
import os

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

class StoredSession(dropbox.session.DropboxSession):
    """a wrapper around DropboxSession that stores a token to a file on disk

    Taken from dropbox cli_client.py example.
    """
    TOKEN_FILE = "token_store.txt"

    def load_creds(self):
        try:
            stored_creds = open(self.TOKEN_FILE).read()
            self.set_token(*stored_creds.split('|'))
            print "[loaded access token]"
        except IOError:
            pass # don't worry if it's not there

    def write_creds(self, token):
        f = open(self.TOKEN_FILE, 'w')
        f.write("|".join([token.key, token.secret]))
        f.close()

    def delete_creds(self):
        os.unlink(self.TOKEN_FILE)

    def link(self):
        request_token = self.obtain_request_token()
        url = self.build_authorize_url(request_token)
        print "url:", url
        print "Please authorize in the browser. After you're done, press enter."
        raw_input()

        self.obtain_access_token(request_token)
        self.write_creds(self.token)

    def unlink(self):
        self.delete_creds()
        session.DropboxSession.unlink(self)


class DropboxHandler(object):

    def __init__(self, APP_KEY, APP_SECRET, ACCESS_TYPE):
        sess = self.session = StoredSession(APP_KEY, APP_SECRET, access_type=ACCESS_TYPE)
        sess.load_creds()
        self.client = dropbox.client.DropboxClient(sess)

    class LoginRequired(Exception):
        def __init__(self, url):
            self.url = url

        
    class FileNotExist(Exception):
        pass

    def dropbox_accessor(func):
        def new_func(self, *args, **kwargs):
            while not self.session.is_linked():
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
    

sync_folder('./test/')
