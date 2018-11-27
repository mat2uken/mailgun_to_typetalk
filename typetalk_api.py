# coding: utf-8

import env

import requests
from requests import Request
import json
from email.utils import parseaddr

def validate_email_address(addr):
    auth = ('api', env.MAILGUN_VALIDATION_KEY)
    VALIDATION_API_URL = 'https://api.mailgun.net/v3/address/validate'

    r = requests.get(VALIDATION_API_URL, auth=auth, params={'addresses': addr})
    if r.status_code != 200:
        abort(500, 'error')

    return json.loads(r.text)

def parse_email_address(addr):
    auth = ('api', env.MAILGUN_VALIDATION_KEY)
    PARSE_API_URL = 'https://api.mailgun.net/v3/address/parse'

    r = requests.get(PARSE_API_URL, auth=auth, params={'addresses': addr})
    if r.status_code != 200:
        abort(500, "parse addr error: {}".format(addr))

    addrjson = json.loads(r.text)

    addrs = []
    for paddr in addrjson['parsed']:
        fullname, addr = parseaddr(paddr)
        addrs.append(addr)

    if not addrs:
        for paddr in addrjson['unparseable']:
            fullname, addr = parseaddr(paddr)
            addrs.append(addr)

    return addrs

def parse_topicid_toaddr(toaddr):
    "Email address validation and extract typetalk topic id by Mailgun API"

    addrs = parse_email_address(toaddr)
    local_part = addrs[0].split('@')[0]

    if local_part is None:
        abort(500, 'email validation failed?: {}'.format(toaddr))

    tidstr = local_part.replace('typetalk-', '')
    topicid = None
    try:
        topicid = int(tidstr)
    except ValueError as e:
        abort(500, 'from address cannot parse as topicid: {}'.format(toaddr))

    return topicid

TYPETALK_API_PREFIX = 'https://typetalk.com/api/v1'
TYPETALK_API_TOPIC_URL = TYPETALK_API_PREFIX + '/topics'
class Typetalk(object):
    def __init__(self, topic_id):
        self.token = self.get_typetalk_credential()
        self.topic_id = topic_id

    def _request(self, url, payload=None, files=None, method='GET'):
        headers = {'Authorization':'Bearer '+ typetalk_accesstoken}
        r = requests.request(method, url, params=payload, files=files, headers=headers)
        if r.status_code == 404:
            return None
        elif r.status_code != 200:
            abort(500, 'typetalk api error: {}'.format(r.text))

        return r.json()

    def _build_topic_api_url(self):
        return '{}/{}'.format(TYPETALK_API_TOPIC_URL, self.topic_id)


    def get_credential(self, scope='topic.read,topic.post,topic.write'):
        url = "https://typetalk.com/oauth2/access_token"
        r = requests.post(url, {'client_id': TYPETALK_CLIENT_ID,
                'client_secret': TYPETALK_CLIENT_SECRET,
                'grant_type': 'client_credentials','scope': scope})
        if r.status_code !=200:
            abort(500, "typetalk api error: status code={}, {}".format(r.status_code, r.text))

        return r.json()['access_token']


    def get_matome_id(self, name):
        url = self._build_topic_api_url() + '/talks'
        talksjson = self._request(url)
        for talk in talksjson['talks']:
            if talk['name'] == name:
                return talk['id']

        return None


    def get_message_id_in_matome(self, message_id):
        talk_id = self.get_typetalk_matome(message_id)
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


    def get_or_create_typetalk_matome(self, name):
        talk_id = self.get_typetalk_matome(name)
        if talk_id is not None:
            return talk_id

        url = self._build_topic_api_url() + '/talks'
        talkjson = self._request(url, {'talkName': name}, method='POST')
        return talkjson['talk']['id']


    def post_to_typetalk(self, message):
        topic = self.get_typetalk_topic_detail()
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
            talkname = addrs.pop(0)
            from_talkid = self.get_or_create_typetalk_matome(talkname)

        addrs = parse_email_address(message.get('toaddr'))
        to_talkid = None
        if addrs:
            local, domain = addrs[0].split('@')
            if 'shiftall.net' in domain:
                talkname = local
            to_talkid = self.get_or_create_typetalk_matome(talkname)

        message_id = message.get('message_id').split('@')[0][1:]
        if len(message_id) >= 64: message_id = message_id[:63]
        message_id_talkid = None
        if message_id is not None:
            message_id_talkid = self.get_or_create_typetalk_matome(message_id)

        # post message
        postmsg = 'メールを受信しました。 --- To: {}\n\n'.format(message.get('toaddr'))
        postmsg += 'From: {}\n件名: 「{}」\n'.format(
                   message.get('fromaddr'),
                   message.get('subject'))
        postmsg += '```\n' + message.get('body') + '\n```\n'
        postmsg += 'Message-ID: {}\n'.format(message.get('message_id'))

        in_reply_to = message.get('in_reply_to')
        if in_reply_to is not None:
            postmsg += 'In-Reply-To: {}\n'.format(in_reply_to)

        references = message.get('references')
        if references is not None:
            postmsg += ' References:\n{}\n'.format(
                '\n'.join(['\t'+x for x in references.split()])
            )

        url = self._build_topic_api_url()
        payload = {'message': postmsg}
        for i, uf in enumerate(uploaded_filekeys):
            payload['fileKeys[{}]'.format(i)] = uf

        if from_talkid is not None:
            payload['talkIds[0]'] = from_talkid
        if to_talkid is not None:
            payload['talkIds[1]'] = to_talkid
        if message_id_talkid is not None:
            payload['talkIds[2]'] = message_id_talkid

        if in_reply_to is not None:
            in_reply_to_id = in_reply_to.split('@')[0][1:]
            if len(in_reply_to_id) >= 64: message_id = message_id[:63]
            payload['replyTo'] = self.get_message_id_in_matome(in_reply_to_id)
        else:
            if references is not None:
                for ref in references.split():
                     ref_id = ref.split('@')[0][1:]
                     if len(ref_id) >= 64: ref_id[:63]
                     msgid = get_message_id_in_matome(self.ref_id)
                     if msgid is None:
                          continue
                     payload['replayTo'] = msgid
                     break

        return self._request(url, params=payload, method='POST')
