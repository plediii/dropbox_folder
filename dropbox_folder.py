
import os
import cPickle as pickle
import shutil
import tempfile

import contextlib as cl
from configuration import configuration

import dropbox
import time

# class DictTokenStore(object):

#     def __init__(self):
#         self.d = {}
    
#     def name(self, namespace, token):
#         return namespace + '_' + token

#     def get(self, namespace, token):
#         name = self.name(namespace, token)

#         try:
#             return self.d[name]
#         except KeyError:
#             return None

#     def set(self, namespace, token, val):
#         name = self.name(namespace, token)

#         self.d[name] = val

# tokenstore = DictTokenStore()


class TextTokenStore(object):

    def __init__(self, name):
        self.token_filename = 'token_store_%s.txt'
        
    def get_creds(self, cred):
        with open(self.token_filename) as f:
            pickle.loads(f.read())
        

class Creds(object):
    def __init__(self, request=None, access=None):
        self.request = request
        self.access = access

class LoginRequired(Exception):
    def __init__(self, url):
        self.url = url
        self.msg = "Please login: %s" % url

    def __str__(self):
        return self.msg




class StoredSession(dropbox.session.DropboxSession):
    """a wrapper around DropboxSession that stores a token to a file on disk

    Based on dropbox cli_client.py example.
    """
    TOKEN_FILE = "token_store.txt"

    def __init__(self, name, *args, **kwargs):
        self.TOKEN_FILE = 'token_store_%s.txt' % name
        self.creds = Creds()
        dropbox.session.DropboxSession.__init__(self, *args, **kwargs)

    def load_creds(self):
        try:
            try:
                self.creds = Creds()
                with open(self.TOKEN_FILE) as f:
                    self.creds = pickle.loads(f.read())
            except EOFError:
                pass

            access = self.creds.access
            if access:
                self.set_token(access.key, access.secret)
                print "[loaded access token]", access.key

            request = self.creds.request
            if request:
                self.set_request_token(request.key, request.secret)
                print "[loaded request token]: ", request.key


        except IOError:
            pass # don't worry if it's not there

    def write_creds(self):
        with open(self.TOKEN_FILE, 'w') as f:
            f.write(pickle.dumps(self.creds))

    def delete_creds(self):
        self.creds = Creds()
        os.unlink(self.TOKEN_FILE)

    def link(self):
        if self.creds.request:
            try:
                self.obtain_access_token(self.creds.request)
                self.creds.access = self.token
                self.write_creds()
                return
            except dropbox.rest.ErrorResponse as e:
                print e
                pass
                    

        request = self.obtain_request_token()
        url = self.build_authorize_url(request)
        self.creds.request = request
        self.write_creds()
        raise LoginRequired(url)

    def unlink(self):
        self.delete_creds()
        session.DropboxSession.unlink(self)


def prepend_slash(path):
    if path == '':
        return '/'
    elif path[0] != '/':
        return '/' + path
    else:
        return path

class FileStore(object):

    def __init__(self, target_path):
        self.target_path = target_path
        self.cursor = None

    def local_path(self, dropbox_path):
        # this isn't really portable...
        if dropbox_path != '' and dropbox_path[0] == '/':
            dropbox_path = dropbox_path[1:]
        local_path =  os.path.join(self.target_path, dropbox_path)
        return local_path
        
    def new_file(self, client, dropboxpath, metadata):
        if metadata['is_dir']:
            os.mkdir(self.local_path(dropboxpath))
            metadata = client.metadata(dropboxpath)
        else:
            with cl.closing(client.get_file(dropboxpath)) as f:
                with open(self.local_path(dropboxpath), 'w') as g:
                    g.write(f.read())

        self.allfiles[metadata['path']] = metadata

        parentpath = self.get_parent(metadata['path'])
        self.allfiles[parentpath] = client.metadata(parentpath)


    def rm_file(self, dropboxpath):
        try:
            metadata = self.allfiles[dropboxpath]
        except KeyError:
            raise self.NotExist(dropboxpath)
        localpath = self.local_path(dropboxpath)
        if metadata['is_dir']:
            os.rmdir(localpath)
        else:
            os.remove(localpath)

        del self.allfiles[dropboxpath]

    class NotExist(Exception):
        pass

    def get_file(self, dropboxpath):
        if dropboxpath in self.allfiles:
            return self.allfiles[dropboxpath]
        else:
            raise NotExist(dropboxpath)

    def get_list(self, dropboxpath):
        if dropboxpath in self.allfiles:
            f = self.allfiles[dropboxpath]
            if f['is_dir']:
                return f['contents']
            else:
                return [f]
        else:
            raise self.NotExist(dropboxpath)


    def get_parent(self, dropboxpath):
        if dropboxpath in self.allfiles:
            last_slash = dropboxpath.rfind('/')
            if last_slash > 0:
                return dropboxpath[:last_slash]
            else:
                return '/'
        else:
            raise self.NotExist(dropboxpath)


    def get_contents(self, dropboxpath):
        if dropboxpath in self.allfiles:
            with open(self.local_path(dropboxpath)) as f:
                return f.read()
        else:
            raise NotExist(dropboxpath)


    def reset(self, client):
        self.allfiles = {}
        self.cursor = None
        target_path = self.target_path
        if os.path.exists(target_path):
            shutil.rmtree(target_path)
        os.mkdir(target_path)
        self.allfiles[u'/'] = client.metadata(u'/')



class FileNotExist(Exception):
    pass

class DropboxHandler(object):

    def __init__(self, name, 
                 file_store,
                 APP_KEY=configuration.dropbox.APP_KEY,
                 APP_SECRET=configuration.dropbox.APP_SECRET,
                 ACCESS_TYPE=configuration.dropbox.ACCESS_TYPE):
        self.name = name
        sess = self.session = StoredSession(name, APP_KEY, APP_SECRET, access_type=ACCESS_TYPE)
        sess.load_creds()
        client = self.client = dropbox.client.DropboxClient(sess)
        self.file_store = file_store
            
        self.synch()


    def close(self):
        self.root.release()

    def dropbox_accessor(func):
        def new_func(self, *args, **kwargs):
            if not self.session.is_linked():
                self.session.link()
            return func(self, *args, **kwargs)
        return new_func

    def logged_in(self):
        return self.session.is_linked()

    @dropbox_accessor
    def synch(self):
        file_store = self.file_store
        client = self.client
        while True:
            delta = client.delta(file_store.cursor)
            if delta['reset']:
                file_store.reset(client)

            for path, metadata in delta['entries']:
                if metadata is None:
                    file_store.rm_file(path)
                else:
                    file_store.new_file(client, path, metadata)

            file_store.cursor = delta['cursor']

            if not delta['has_more']:
                break

    @property
    def target_path(self):
        return self.file_store.target_path


    @dropbox_accessor
    def login(self):
        pass


    @dropbox_accessor
    def list(self, path='/'):
        if path != '/' and path[-1] == '/':
            path = path[:-1]
        self.synch()
        try:
            return self.file_store.get_list(path)
        except self.file_store.NotExist:
            raise FileNotExist(path)

    @dropbox_accessor
    def contents(self, path):
        self.synch()
        try:
            return self.file_store.get_contents(path)
        except file_store.NotExist:
            raise FileNotExist(path)


def test_list(handler, target_path):
    print '****listing "%s"' % target_path

    print handler.list(target_path)


if __name__ == "__main__":
    print 'testing...'
    handler = DropboxHandler('test', 
                             file_store=FileStore('./test/'))

    test_list(handler, '/')
    # test_list(handler, '/subtest')
    # test_list(handler, '/subtest/')
    # test_list(handler, '/subtest/subsubtest')
    # test_list(handler, '/subtest/samplefile.tex')
    # test_list(handler, '/subtest/subsubtest/helloo.tex')
    # handler.close()
    # handler.sync_folder()
