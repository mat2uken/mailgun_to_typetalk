# coding: utf-8

from localenv import *

import requests
from requests import Request
from email.utils import parseaddr

#import logging
#logging.basicConfig(level=logging.DEBUG)

def validate_email_address(addr):
    auth = ('api', MAILGUN_VALIDATION_KEY)
    VALIDATION_API_URL = 'https://api.mailgun.net/v3/address/validate'

    r = requests.get(VALIDATION_API_URL, auth=auth, params={'addresses': addr})
    if r.status_code != 200:
        raise TypetalkException('mailgun validation api error: {}'.format(r.text))

    return r.json()

def parse_email_address(addr):
    auth = ('api', MAILGUN_VALIDATION_KEY)
    PARSE_API_URL = 'https://api.mailgun.net/v3/address/parse'

    r = requests.get(PARSE_API_URL, auth=auth, params={'addresses': addr})
    if r.status_code != 200:
        raise TypetalkException("mailgun parse addr api error: {}".format(addr))

    addrjson = r.json()
    addrs = []
    for paddr in addrjson['parsed']:
        fullname, addr = parseaddr(paddr)
        addrs.append(addr)

    if not addrs:
        for paddr in addrjson['unparseable']:
            fullname, addr = parseaddr(paddr)
            addrs.append(addr)

    return addrs

def get_topic_id_from_toaddr(toaddr):
    "Parse e-mail addresses and extract typetalk topic id by Mailgun API"

    addrs = parse_email_address(toaddr)
    local_part = addrs[0].split('@')[0]

    if local_part is None:
        raise TypetalkException('email validation failed?: {}'.format(toaddr))

    tidstr = local_part.replace('typetalk-', '')
    topicid = None
    try:
        topicid = int(tidstr)
    except ValueError as e:
        raise TypetalkException('from address cannot parse as topicid: {}'.format(toaddr))

    return topicid

class TypetalkException(Exception):
    pass

TYPETALK_API_PREFIX = 'https://typetalk.com/api/v1'
TYPETALK_API_TOPIC_URL = TYPETALK_API_PREFIX + '/topics'
class TypetalkAPI(object):
    def __init__(self, topic_id):
        self.token = self.get_credential()
        self.topic_id = topic_id

    def _request(self, url, params=None, data=None, files=None, method='GET'):
        headers = {'Authorization':'Bearer '+ self.token}
        r = requests.request(method, url, params=params, data=data, files=files, headers=headers)
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
        url = self._build_topic_api_url() + '/talks'
        talksjson = self._request(url)
        for talk in talksjson['talks']:
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
        return talkjson['talk']['id']


    def post_message(self, message):
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
                r = self._request(url, files=payload, method='POST')
                if r is not None:
                    uploaded_filekeys.append(r.get('fileKey'))

        # get or create matome
        addrs = parse_email_address(message.get('fromaddr'))
        from_talkid = None
        if addrs:
            local, domain = addrs[0].split('@')
            if 'shiftall.net' not in domain:
                from_talkid = self.get_or_create_matome(addrs[0])

        addrs = parse_email_address(message.get('toaddr'))
        to_talkid = None
        if addrs:
            local, domain = addrs[0].split('@')
            if 'shiftall.net' not in domain:
                to_talkid = self.get_or_create_matome(addrs[0])

        message_id = message.get('message_id').split('@')[0][1:]
        if len(message_id) >= 64: message_id = message_id[:63]
        message_id_talkid = None
        if message_id is not None:
            message_id_talkid = self.get_or_create_matome(message_id)

        # post message
        postmsg = 'メールを受信しました。 --- To: {}\n\n'.format(message.get('toaddr'))
        postmsg += 'From: {}\n件名: 「{}」\n'.format(
                   message.get('fromaddr'),
                   message.get('subject'))
        postmsg += '```\n' + message.get('body') + '\n```\n'

        payload = {'message': postmsg}
        for i, uf in enumerate(uploaded_filekeys):
            payload['fileKeys[{}]'.format(i)] = uf

        if from_talkid is not None:
            payload['talkIds[0]'] = from_talkid
        if to_talkid is not None:
            payload['talkIds[1]'] = to_talkid
        if message_id_talkid is not None:
            payload['talkIds[2]'] = message_id_talkid

        in_reply_to = message.get('in_reply_to')
        references = message.get('references')
        if in_reply_to is not None:
            in_reply_to_id = in_reply_to.split('@')[0][1:]
            if len(in_reply_to_id) >= 64: message_id = message_id[:63]
            payload['replyTo'] = self.get_message_id_in_matome(in_reply_to_id)
        else:
            if references is not None:
                for ref in references.split():
                     ref_id = ref.split('@')[0][1:]
                     if len(ref_id) >= 64: ref_id[:63]
                     msgid = self.get_message_id_in_matome(ref_id)
                     if msgid is None:
                          continue
                     payload['replayTo'] = msgid
                     break

        url = self._build_topic_api_url()
        return self._request(url, data=payload, method='POST')
