# -*- coding: utf-8 -*-
"""
    eve_fsstorage.media.
    ~~~~~~~~~~~~~~~~~~~~

    Filesystem media storage for Eve-powered APIs.

    :copyright: (c) 2016 by CONABIO (JMB@Ecoinfomatica)
    :license: See LICENSE_ADDITIONAL.md for more details.
"""
import tempfile
import os
from shutil import copy
import hashlib
import datetime
from bson import ObjectId

from flask import Flask
from werkzeug.utils import secure_filename
from eve.io.media import MediaStorage
from eve.io.mongo import Mongo
from eve.utils import str_type

# BLOCKSIZE value to efficently calculate the MD5 of a file
BLOCKSIZE = 104857600


def get_md5(file_path):
    """Helper function to calculate MD5 value for a given file.

    :param file_path: File path.
    """
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(BLOCKSIZE)

    return hasher.hexdigest()


class FileSource():

    """FileSource is a file object with metadata.

    This class is created to work as a file interface for
    :class:`FileSystemMediaStorage`.
    """

    def __init__(self, fp, content_type, upload_date, filename, length,
                 original_filename, _id, md5, *args, **kwargs):
        """Constructor."""
        self.content_type = content_type
        self.upload_date = upload_date
        self.filename = filename
        self.length = length
        self.original_filename = original_filename
        self._id = _id
        self.md5 = md5
        fd = os.open(fp, os.O_RDONLY)
        self._file = os.fdopen(fd, 'rb')

    def __getattr__(self, attr):
        return getattr(self._file, attr)

    def __iter__(self):
        return self._file.__iter__()


class FileSystemMediaStorage(MediaStorage):

    """The File System class stores files into disk.

    It uses the MEDIA_PATH configuration value.
    """

    def __init__(self, app=None):
        """Constructor.

        :param app: the flask application (eve itself). This can be used by
        the class to access, amongst other things, the app.config object to
        retrieve class-specific settings.
        """
        super(FileSystemMediaStorage, self).__init__(app)

        self.validate()
        self._fs_path = self.app.config['MEDIA_PATH']
        self._fs_collection = {}

    def validate(self):
        """Make sure that the application data layer is a eve.io.mongo.Mongo
        instance.
        """
        if self.app is None:
            raise TypeError('Application object cannot be None')

        if not isinstance(self.app, Flask):
            raise TypeError('Application object must be a Eve application')

        if not self.app.config.get('MEDIA_PATH'):
            raise KeyError('MEDIA_PATH is not configured on app settings')

    def fs_collection(self, resource=None):
        """ Provides the instance-level Mongo collection to save the data associated
        to saved filesystem, instantiating it if needed.
        """
        driver = self.app.data
        if driver is None or not isinstance(driver, Mongo):
            raise TypeError("Application data object must be of eve.io.Mongo ")

        px = driver.current_mongo_prefix(resource)
        # Collection name will be {resource_name}_files
        collection = '{}_files'.format(resource)

        if px not in self._fs_collection:
            self._fs_collection[px] = driver.pymongo(prefix=px).db[collection]

        return self._fs_collection[px]

    def get(self, _id, resource=None):
        """Return a FileSource object given by unique id. Returns None if no
        file was found.
        """
        self.app.logger.debug('resource: {}, _id:{}'.format(resource, _id))

        if isinstance(_id, str_type):
            # Convert to unicode because ObjectId() interprets 12-chacracter
            # strings (but no unicode) as binary respresentation of ObjectId.
            try:
                _id = ObjectId(unicode(_id))
            except NameError:
                _id = ObjectId(_id)

        _file = None

        try:
            _file = self.fs_collection(resource).find_one({"_id": _id})
        except:
            pass

        # Add filepath to a _file object
        _file.update({'fp': os.path.join(self._fs_path, _file['filename'])})
        _file = FileSource(**_file)

        return _file

    def put(self, content, filename=None, content_type=None, resource=None):
        """ Saves a new file in disk. Returns the unique id of the stored
        file. Also stores content typ, length, md5, filename and upload date of
        the file.
        """
        fd, fp = tempfile.mkstemp()
        content.save(fp)

        file_doc = {'content_type': content_type, 'length': None, 'md5': None,
                    'original_filename': None,
                    'upload_date': datetime.datetime.utcnow(),
                    'filename': None}

        file_doc['md5'] = get_md5(fp)

        try:
            file_doc['original_filename'] = secure_filename(filename)
        except AttributeError:
            file_doc['original_filename'] = secure_filename(content.filename)

        file_doc['length'] = os.path.getsize(fp)

        if not file_doc['content_type']:
            file_doc['content_type'] = content.content_type

        fs_collection = self.fs_collection(resource)

        item_id = fs_collection.insert_one(file_doc).inserted_id

        saved_file = '{oid}_{filename}'.format(oid=item_id,
                                               filename=filename)
        fs_collection.update_one({'_id': item_id}, {'$set': {'filename': saved_file}})

        full_path = os.path.join(self._fs_path, saved_file)
        copy(fp, full_path)
        os.close(fd)
        os.remove(fp)

        return item_id
