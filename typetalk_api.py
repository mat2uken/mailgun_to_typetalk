# coding: utf-8

from localenv import *

import re
import requests
from requests import Request, Session
from email.utils import parseaddr
from urllib.parse import urlencode


def get_topic_id_from_toaddr(toaddr):
    "Parse e-mail addresses and extract typetalk topic id by Mailgun API"

    addrs = toaddr.replace(' ', '').split(',')
    fullname, addr = parseaddr(addrs[0])
    local_part = addr.split('@')[0]

    if local_part is None:
        raise TypetalkException('email validation failed?: {}'.format(toaddr))

    tidstr = local_part.replace('typetalk-', '')
    topicid = None
    try:
        topicid = int(tidstr)
    except ValueError as e:
        raise TypetalkException('from address cannot parse as topicid: {}'.format(toaddr))

    return topicid


from google.cloud import datastore
class MessageStore(object):
    def __init__(self):
        self.client = datastore.Client()

    def save(self, msg_id, msg_url, typetalk_post_id):
        entity_key = self.client.key(CLOUD_STORE_KIND, msg_id)
        msg = datastore.Entity(entity_key,
                exclude_from_indexes=('msg_url', 'typetalk_post_id'))
        msg['msg_id'] = msg_id
        msg['msg_url'] = msg_url
        msg['typetalk_post_id'] = typetalk_post_id
        self.client.put(msg)

    def get_entity(self, msg_id):
        entity_key = self.client.key(CLOUD_STORE_KIND, msg_id)
        return self.client.get(entity_key)


class TypetalkException(Exception):
    pass


TYPETALK_API_PREFIX = 'https://typetalk.com/api/v1'
TYPETALK_API_TOPIC_URL = TYPETALK_API_PREFIX + '/topics'
class TypetalkAPI(object):
    def __init__(self, topic_id):
        self.token = self.get_credential()
        self.topic_id = topic_id
        self.cached_talks = None

    def _upload_request(self, url, files):
        headers = {'Authorization':'Bearer '+ self.token}

        filename = files['file'][0]

        def hack_filename_encode(prepared_request):
            prepared_request.body = re.sub(b'filename\*=.*', b'filename=' + filename.encode('utf-8'), prepared_request.body)
            return prepared_request

        r = requests.post(url, files=files, headers=headers, auth=hack_filename_encode)
        if r.status_code == 404:
            return None
        elif r.status_code != 200:
            raise TypetalkException('typetalk api error: status={}, \n{}'.format(r.status_code, r.text))

        return r.json()


    def _request(self, url, params=None, data=None, method='GET'):
        headers = {'Authorization':'Bearer '+ self.token}
        r = requests.request(method, url, params=params, data=data, headers=headers)
        if r.status_code == 404:
            return None
        elif r.status_code != 200:
            raise TypetalkException('typetalk api error: status={}, \n{}'.format(r.status_code, r.text))

        return r.json()

    def _build_topic_api_url(self):
        return '{}/{}'.format(TYPETALK_API_TOPIC_URL, self.topic_id)


    def get_credential(self, scope='topic.read,topic.post,topic.write'):
        url = "https://typetalk.com/oauth2/access_token"
        r = requests.post(url,
                {'client_id': TYPETALK_CLIENT_ID,
                 'client_secret': TYPETALK_CLIENT_SECRET,
                 'grant_type': 'client_credentials','scope': scope})
        if r.status_code !=200:
            raise TypetalkException("typetalk api error: status={}, {}".format(r.status_code, r.text))

        return r.json()['access_token']


    def get_matome(self, name):
        if self.cached_talks is None:
            url = self._build_topic_api_url() + '/talks'
            self.cached_talks = self._request(url)

        for talk in self.cached_talks['talks']:
            if talk['name'] == name:
                return talk['id']

        return None


    def get_message_id_in_matome(self, message_id):
        talk_id = self.get_matome(message_id)
        if talk_id is None:
            return None

        url = self._build_topic_api_url() + '/talks/{}/posts'.format(talk_id)
        postsjson = self._request(url, {'count': 1})
        for post in postsjson['posts']:
            return post['id']

        return None


    def get_topic_detail(self):
        url = self._build_topic_api_url() + '/details'
        return self._request(url)


    def get_or_create_matome(self, name):
        talk_id = self.get_matome(name)
        if talk_id is not None:
            return talk_id

        url = self._build_topic_api_url() + '/talks'
        print('creating matome: {}, talkName: {}'.format(url, name))
        talkjson = self._request(url, data={'talkName': name}, method='POST')
        self.cached_talks = None
        return talkjson['talk']['id']


    def post_message(self, message, message_url=None):
        topic = self.get_topic_detail()
        if topic is None:
            print("topic is not found. change topic id to default(97119)")
            self.topic_id = 97119

        # upload attachments
        uploaded_filekeys = []
        attachments = message.get('attachments')
        if attachments is not None:
            for a in attachments:
                url = self._build_topic_api_url() + '/attachments'
                payload = {'file': (a['name'], a['content'], a['content_type'])}

                r = self._upload_request(url, files=payload)
                if r is not None:
                    uploaded_filekeys.append(r.get('fileKey'))

        # post message
        postmsg = 'メールを受信しました。 --- To: {}\n\n'.format(message.get('toaddr'))
        postmsg += 'From: {}\n件名: 「{}」\n'.format(
                   message.get('fromaddr'),
                   message.get('subject'))

        body = message.get('body')
        view_message_continue = None
        if len(body) > 3500:
            body = body[:3500] + '\n'
            if message_url is not None:
                query = urlencode({'message_id': message.get('message_id')})
                view_message_continue = \
                '''省略されました。 [>>>全文(text)を見る]({})\n'''.format(
                    VIEW_MESSAGE_CONTINUE_URL+'?{}'.format(query)
                )

        postmsg += '```\n' + body + '\n```\n'
        if view_message_continue is not None:
            postmsg += view_message_continue + '\n'

        payload = {'message': postmsg}
        for i, uf in enumerate(uploaded_filekeys):
            payload['fileKeys[{}]'.format(i)] = uf

        if view_message_continue is not None:
            payload['showLinkMeta'] = 'false'

        ms = MessageStore()
        in_reply_to = message.get('in_reply_to')
        references = message.get('references')
        if in_reply_to is not None:
            message_entity = ms.get_entity(in_reply_to)
            if message_entity is not None:
                payload['replyTo'] = message_entity['typetalk_post_id']
        else:
            if references is not None:
                for ref in references.split():
                    if ref == message.get('message_id'):
                        message_entity = ms.get_entity(ref)
                        payload['replayTo'] = message_entity['typetalk_post_id']
                        break

        url = self._build_topic_api_url()
        return self._request(url, data=payload, method='POST')
