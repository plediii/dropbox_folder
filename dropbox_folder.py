
import os
import cPickle as pickle
import shutil
import tempfile

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

class DropboxFolder(object):
    """Invariant: contents of file in path corresponds to metadata."""

    class NotExist(Exception):
        pass

    def __init__(self, target_path, path):
        path = prepend_slash(path)
        if path[-1] == '/':
            path = path[:-1]
        
        self.path = path
        self.target_path = target_path
        self.local_path = os.path.join(target_path, path[1:])

        self.files = []
        self.metadata = {'path': path,
                         'is_dir': False}


    def synch(self, client):
        print 'synchronizing ', self.local_path
        try:
            self.metadata = client.metadata(self.path)
        except dropbox.rest.ErrorResponse as e:
            if e.status == 404:
                raise self.NotExist(path)
            else:
                raise

        # make the local directory to hold the files
        try:
            os.mkdir(self.local_path)
        except OSError:
            pass
        # download each of the files in the dropbox folder
        self.files = []
        for meta in self.metadata['contents']:
            if meta['is_dir']:
                f = DropboxFolder(self.target_path, meta['path'])
            else:
                f = DropboxFile(self.target_path, meta['path'])

            f.synch(client)
            self.files.append(f)
            

    def __str__(self):
        return '< dropbox::%s >' % self.path


    def __repr__(self):
        return "DropboxFolder('%s', '%s')" % (self.target_path, self.path)


    def metadata(self):
        return self.metadata

    def list(self, subpath=''):
        print 'looking for list of "%s"' % subpath
        print 'below "%s"' % (self.path)
        subpath = prepend_slash(subpath)[1:]
        print 'normalized "%s"' % subpath

        if subpath == '':
            return self.files

        if subpath.find('/') >= 0:
            # list in sub directory
            path, rest = subpath.split('/', 1)
            path = path
        else:
            path = subpath
            rest = None


        path = self.path + '/' + path

        for f in self.files:
            print 'comparing "%s" while searching for "%s"' % (f.path, path)
            if f.path == path:
                if rest is None:
                    return [f]
                else:
                    print 'Descending to path "%s"' % (f.path, )
                    return f.list(rest)
            
        raise self.NotExist(path)
            


    def release(self):
        for f in self.files:
            f.release()
        os.rmdir(self.local_path)
            

    

class DropboxFile(object):
    """Invariant: contents of file in path corresponds to metadata."""

    class NotExist(Exception):
        pass

    def __init__(self, target_path, path):
        path = prepend_slash(path)
        self.path = path
        self.target_path = target_path
        self.local_path = os.path.join(target_path, path[1:])

        self.metadata = {'path': path, 
                         'is_dir': False}


    def synch(self, client):
        try:
            f, self.metadata = client.get_file_and_metadata("/" + self.path)
        except dropbox.rest.ErrorResponse as e:
            if e.status == 404:
                raise self.NotExist(path)
            else:
                raise
        else:
            print 'synchronizing ', self.local_path
            with open(self.local_path, 'w')  as localf:
                localf.write(f.read())

    def __str__(self):
        return '< dropbox::%s >' % self.path


    def __repr__(self):
        return "DropboxFile('%s', '%s')" % (self.target_path, self.path)


    def contents(self):
        if os.path.exists(self.local_path):
            with open(self.local_path) as f:
                return f.read()
        else:
            raise Exception("not reachable")
        
    def metadata(self):
        return self.metadata


    def release(self):
        os.remove(self.local_path)
            
            
# class LocalFolderStore(object):

#     def __init__(self, target_path=None, keep=None):
#         if target_path is None:
#             target_path = tempfile.mkdtemp(name)
#             if keep is None:
#                 keep = False
#         else:
#             if keep is None:
#                 keep = True

#         storepath = self.storepath = os.path.join(target_path, '.dfstore')

#         if os.path.exists(storepath):
#             with open(storepath) as f:
#                 self.rootpath = pickle.loads(f.read())
#         else:
#             self.rootpath = 


#     def close(self):
#         if self.keep:
#             self.commit()
#             return
#         else:
#             self.rootpath.release()
        
     


class DropboxHandler(object):

    def __init__(self, name, 
                 target_path=None,
                 keep=None,
                 APP_KEY=configuration.dropbox.APP_KEY,
                 APP_SECRET=configuration.dropbox.APP_SECRET,
                 ACCESS_TYPE=configuration.dropbox.ACCESS_TYPE):
        self.name = name
        sess = self.session = StoredSession(name, APP_KEY, APP_SECRET, access_type=ACCESS_TYPE)
        sess.load_creds()
        client = self.client = dropbox.client.DropboxClient(sess)
            
        if target_path is None:
            if keep is None:
                keep = False
            target_path = tempfile.mkdtemp(name)
        elif keep is None:
            keep = True
        self.target_path = target_path

        self.root = DropboxFolder(target_path, '/')

        # self.root.synch(client)


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
    def login(self):
        pass


    @dropbox_accessor
    def list(self, path='/'):            
        self.root.synch(self.client)
        return self.root.list(path)


    @dropbox_accessor
    def contents(self, path):
        self.root.synch(self.client)
        if path[0] != '/':
            path = '/' + path

        if path in self.file_state:
            return 


            try:
                f, metadata = self.client.get_file_and_metadata("/" + path)
            except dropbox.rest.ErrorResponse as e:
                if e.status == 404:
                    raise self.FileNotExist(path)
                else:
                    raise
            # print 'Metadata:', metadata
            return f.read()


    def sync_folder(self):

        if self.file_state == {}:
            l = self.list()

            for f in l:
                if not f['is_dir']:
                    path = f['path']
                    to_path = os.path.join(target_path, path[1:])
                    filename = os.path.expanduser(to_path)
                    print 'Downloading...', filename
                    try:
                        contents = self.contents(path)
                    except:
                        print 'exception on ', f
                        raise
                    with open(filename, "wb") as to_file:
                        to_file.write(contents)

        else:
            print 'I dont do resyncs...'

def test_list(handler, target_path):
    print 'listing "%s"' % target_path

    handler.list(target_path)


if __name__ == "__main__":
    print 'testing...'
    handler = DropboxHandler('test', target_path='./test/')
    test_list(handler, '/')
    test_list(handler, '/subtest')
    test_list(handler, '/subtest/')
    test_list(handler, '/subtest/subsubtest')
    test_list(handler, '/subtest/samplefile.tex')
    test_list(handler, '/subtest/subsubtest/helloo.tex')
    # handler.close()
    # handler.sync_folder()
