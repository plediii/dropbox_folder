
import os

import configuration

import dropbox
import time

class DictTokenStore(object):

    def __init__(self):
        self.d = {}
    
    def name(self, namespace, token):
        return namespace + '_' + token

    def get(self, namespace, token):
        name = self.name(namespace, token)

        try:
            return self.d[name]
        except KeyError:
            return None

    def set(self, namespace, token, val):
        name = self.name(namespace, token)

        self.d[name] = val

tokenstore = DictTokenStore()

class DropboxHandler(object):

    def __init__(self, APP_KEY, APP_SECRET, ACCESS_TYPE):
        sess = self.session = dropbox.session.DropboxSession(APP_KEY, APP_SECRET, ACCESS_TYPE)

        self.__client = None


    def get_client(self):
        if self.__client:
            return self.__client

        access_token = self.get_access_token()
        if access_token:
            self.session.token = access_token
            self.__client = dropbox.client.DropboxClient(self.session)
            return self.__client

        return None
            

    def set_request_token(self, request_token):
        tokenstore.set('dropbox', 'request', request_token)        

    def new_request_token(self):
        request_token = self.session.obtain_request_token()
        self.set_request_token(request_token)
        return request_token

    def get_request_token(self):
        request_token = tokenstore.get('dropbox', 'request')
        if request_token:
            return request_token
        return self.new_request_token()

    def new_access_token(self):
        request_token = self.get_request_token()
        access_token=self.session.obtain_access_token(request_token)
        tokenstore.set('dropbox', 'access', access_token)
        return access_token

    def get_access_token(self):
        access_token = tokenstore.get('dropbox', 'access')
        if access_token:
            return access_token
        return self.new_access_token()


    def dropbox_accessor(func):
        def new_func(self, *args, **kwargs):
            exc = 'None'
            try:
                login = None
                val = None
                val = func(self, *args, **kwargs)
                status = True
            except rest.ErrorResponse, e:
                request_token = self.new_request_token()
                login = self.session.build_authorize_url(request_token)
                status = False
                exc = str(e)
            result = {'success': status,
                        'value': val,
                        'exc': exc}
            if login:
                    result['login'] = login
            return result
        return new_func


    @dropbox_accessor
    def list(self, path='/'):
        cli = self.get_client()
        return [meta for meta  in cli.metadata(path)['contents']]


    @dropbox_accessor
    def contents(self, path):
        cli = self.get_client()
        return cli.get_file_and_metadata(path)[0].read()
            

dropboxhandler = DropboxHandler(APP_KEY=configuration.dropbox.APP_KEY,
                               APP_SECRET=configuration.dropbox.APP_SECRET,
                               ACCESS_TYPE=configuration.dropbox.ACCESS_TYPE)


print dropboxhandler.list()
