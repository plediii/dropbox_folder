
import os
import cPickle as pickle

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


class DropboxHandler(object):

    def __init__(self, APP_KEY, APP_SECRET, ACCESS_TYPE):
        sess = self.session = StoredSession('', APP_KEY, APP_SECRET, access_type=ACCESS_TYPE)
        sess.load_creds()
        self.client = dropbox.client.DropboxClient(sess)


        
    class FileNotExist(Exception):
        pass

    def dropbox_accessor(func):
        def new_func(self, *args, **kwargs):
            if not self.session.is_linked():
                self.session.link()
            return func(self, *args, **kwargs)
        return new_func


    @dropbox_accessor
    def list(self, path='/'):
        return [meta for meta  in self.client.metadata(path)['contents']]


    @dropbox_accessor
    def contents(self, path):
        try:
            f, metadata = self.client.get_file_and_metadata("/" + path)
        except dropbox.rest.ErrorResponse as e:
            if e.status == 404:
                raise self.FileNotExist(path)
            else:
                raise
        # print 'Metadata:', metadata
        return f.read()
            

dropboxhandler = DropboxHandler(APP_KEY=configuration.dropbox.APP_KEY,
                               APP_SECRET=configuration.dropbox.APP_SECRET,
                               ACCESS_TYPE=configuration.dropbox.ACCESS_TYPE)




def sync_folder(target_path):
    l = dropboxhandler.list()


    for f in l:
        if not f['is_dir']:
            path = f['path']
            to_path = os.path.join(target_path, path[1:])
            filename = os.path.expanduser(to_path)
            print filename
            try:
                contents = dropboxhandler.contents(path)
            except:
                print 'excetion on ', f
                raise
            with open(filename, "wb") as to_file:
                to_file.write(contents)
    
if __name__ == "__main__":
    print 'testing...'
    sync_folder('./test/')
