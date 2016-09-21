'''
    TFS REST API CLIENT
    Author: Deunze
'''

import traceback
import json
import urllib2
from ntlm import HTTPNtlmAuthHandler

class Workitem(object):
    
    def __init__(self):
        self.fields = []
    
    def addField(self, path, value):
        self.fields.append({
            'op': 'add',
            'path': path,
            'value': value
        })
    
    def removeField(self, path):
        for field in self.fields:
            if path == field['path']:
                self.fields.remove(field)
                return True
        return False
    
    def addRelationship(self, value):
        self.fields.append({
            'op': 'add',
            'path': '/relations/-',
            'value': value
        })
        
    def addAttachementRel(self, url):
        self.addRelationship({
            'rel': 'AttachedFile',
            'url': url
        })
    
    def get(self):
        return self.fields

class TFSClientAPI(object):
    def __init__(self, domain, username, password, hostname, port, collection, debug=None):
        self.domain = domain
        self.username = username
        self.password = password
        self.hostname = hostname
        self.debug = debug
        if port == 80:
            self.URL = "https://%s/%s/_apis/" % (hostname, collection)
        else:
            self.URL = "https://%s:%d/%s/_apis/" % (hostname, port, collection)
        self.PARAMETERS = {
            'api-version': '1.0'
        }
        self.MAX_ITEMS_PER_QUERY = 200
        self.init()
    
    def init(self):
        self.AUTH_MGR = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.AUTH_MGR.add_password(
            None, 
            "https://%s/" % (self.hostname), 
            r'%s\%s' % (self.domain, self.username), 
            self.password
        )
        self.AUTH = HTTPNtlmAuthHandler.HTTPNtlmAuthHandler(self.AUTH_MGR)
        self._handler = urllib2.HTTPHandler(debuglevel=self.debug)
        self._opener = urllib2.build_opener(self.AUTH)
        urllib2.install_opener(self._opener)

    def set_parameter(self, parameter, value):
        self.PARAMETERS[parameter] = value
    
    def unset_parameter(self, parameter):
        if parameter in self.PARAMETERS:
            del self.PARAMETERS[parameter]
    
    def reset_parameters(self):
        parameters = ["$expand", "fields", "ids"]
        for param in parameters:
            self.unset_parameter(param)

    def set_resource(self, resource, project=None):
        url = self.URL
        if project:
            url = url.replace('_apis', project + '/_apis')
        self.resource = url + resource
        return self
    
    def _compose_resource_path(self):
        full_resource_url = self.resource
        get_args = '&'.join([
            '%s=%s' % (k, v)
            for k, v in self.PARAMETERS.iteritems()
        ])
        if get_args:
            full_resource_url = full_resource_url + '?' + get_args
        return full_resource_url
    
    def _convert(self, data):
        return json.dumps(data)
    
    def _log_status(self, error):
        raise Exception('Not implemented!')
    
    def prepare(self, data=None, method='GET', type='application/json'):
        full_resource_url = self._compose_resource_path()
        if data:
            data = self._convert(data)
        if self.debug:
            print(full_resource_url)
        request = urllib2.Request(full_resource_url, data if data else None, {'Content-Type': type})
        request.get_method = lambda: method
        return request
    
    def fire(self, request):
        try:
            connection = urllib2.urlopen(request)
        except urllib2.HTTPError, e:
            connection = e
        if connection.code == 200:
            for i in [1,2,3]:
                try:
                    read = connection.read()
                    if self.debug:
                        print(connection.info())
                    return read
                except Exception, e:
                    reason = str(traceback.format_exc())
        else:
            if hasattr(connection, 'reason'):
                reason = connection.reason
            else:
                reason = connection.read()
        error = 'TFSClientAPI: HTTP Error '+str(connection.code)+' ('+str(reason)+')'
        self._log_status(error)
        return False
    
    def read(self, response):
        self.reset_parameters()
        try:
            return json.loads(response) if response else False
        except Exception, e:
            return {
                'status': 'Error',
                'message': 'Exception error: %s' % e
            }
    
    ''' ============================
    #   TFS METHODS
    ============================ '''
    
    def perform_query(self, wiql_query, project=None):
        self.set_resource('wit/wiql', project)
        request = self.prepare({"query": wiql_query}, 'POST')
        response = self.fire(request)
        return self.read(response)
    
    # Workitem methods
    
    def get_workitem(self, id=None, expand=None):
        path = 'wit/workitems'
        if id:
            path += '/' + str(id)
        if expand:
            self.set_parameter('$expand', expand)
        self.set_resource(path)
        request = self.prepare()
        response = self.fire(request)
        return self.read(response)
    
    def get_workitems(self, ids, fields=None):
        res = []
        for i in xrange(0, len(ids), self.MAX_ITEMS_PER_QUERY):
            ids_chunk = ids[i:i+self.MAX_ITEMS_PER_QUERY]
            self.set_parameter('ids', ','.join(str(x) for x in ids_chunk))
            if fields:
                self.set_parameter('fields', ','.join(fields))
            self.set_resource('wit/workitems')
            request = self.prepare()
            response = self.fire(request)
            read = self.read(response)
            if read and 'value' in read:
                if i == 0:
                    res = read
                else:
                    for wit in read['value']:
                        res['value'].append(wit)
                    
        return res              
    
    def create_workitem(self, wit, type, project):
        path = 'wit/workitems/$' + type
        self.set_resource(path, project)
        request = self.prepare(wit, 'PATCH', 'application/json-patch+json')
        response = self.fire(request)
        return self.read(response)
    
    def update_workitem(self, id, wit):
        self.set_resource('wit/workitems/' + str(id))
        request = self.prepare(wit, 'PATCH', 'application/json-patch+json')
        response = self.fire(request)
        return self.read(response)
    
    def upload_attachment(self, filename, filecontent):
        self.set_resource('wit/attachments')
        self.set_parameter('filename', filename)
        request = self.prepare(filecontent, 'POST')
        response = self.fire(request)
        return self.read(response)
