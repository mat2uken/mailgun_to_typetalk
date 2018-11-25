# [START gae_python37_app]
from flask import Flask
from flask import abort, request

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

import os

MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
MAILGUN_VALIDATION_KEY = os.environ.get('MAILGUN_VALIDATION_KEY')
TYPETALK_CLIENT_ID = os.environ.get('TYPETALK_CLIENT_ID')
TYPETALK_CLIENT_SECRET = os.environ.get('TYPETALK_CLIENT_SECRET')

if os.environ.get('GAE_ENV') != 'standard':
    import yaml
    data = yaml.load(open('secret.yaml'))
    env = data['env_variables']
    MAILGUN_API_KEY = env['MAILGUN_API_KEY']
    MAILGUN_VALIDATION_KEY = env['MAILGUN_VALIDATION_KEY']
    TYPETALK_CLIENT_ID = env['TYPETALK_CLIENT_ID']
    TYPETALK_CLIENT_SECRET = env['TYPETALK_CLIENT_SECRET']

print('MAILGUN_API_KEY: {}'.format(MAILGUN_API_KEY))
print('MAILGUN_VALIDATION_KEY: {}'.format(MAILGUN_VALIDATION_KEY))
print('TYPETALK_CLIENT_ID: {}'.format(TYPETALK_CLIENT_ID))
print('TYPETALK_CLIENT_SECRET: {}'.format(TYPETALK_CLIENT_SECRET))

import requests
import json
from email.utils import parseaddr

@app.route('/')
def hello():
    """Return a friendly HTTP greeting."""
    return 'Hello World!'


@app.route('/recv_email', methods=['POST'])
def recv_email():
    "Receive from mailgun as HTTP request"

    message_id = request.form.get('Message-Id')
    print('Start processing message: {}'.format(message_id))

    message_url = request.form.get('message-url')
    print('notified message-url: {}'.format(message_url))

    topicid, message = get_message_from_mailgun(message_url)
    print("received message to Typetalk({}): {}".format(topicid, message['body']))

    ret = post_to_typetalk(topicid, message)
    print("post to typetalk is succeeded: {}".format(str(ret)))

    return 'OK'


def get_message_from_mailgun(message_url):
    "Get message and attachments from Mailgun API"

    auth = ('api', MAILGUN_API_KEY)
    message = requests.get(message_url, auth=auth)
    if message.status_code != 200:
        abort(500, "cannnot get message from mailgun: {}".format(message_url))

    msgjson = json.loads(message.text)

    fromaddr = msgjson.get('X-Original-From')
    if fromaddr is None:
        fromaddr = msgjson.get('From')

    toaddr = msgjson.get('To')
    recipients = msgjson.get('recipients')
    sender = msgjson.get('sender')
    subject = msgjson.get('subject')
    print('from: {}, to: {}, recipients: {}, sender: {}'.format(
        fromaddr, toaddr, recipients, sender
    ))

    # Typetalkのtopicはfromのtypetalk-xxxxのxxxxをidとしてtopicを特定
    topicid = parse_topicid_toaddr(recipients)
    if topicid is None:
        abort(500, 'To addr is not valid as topic id: {}'.format(toaddr))
    else:
        print("Target topic id: {}".format(topicid))

    body_plain = msgjson.get('body-plain')
    stripped_text = msgjson.get('stripped-text')

    attachments = []
    for attachment in msgjson.get('attachments'):
        content_type = attachment.get('content-type')
        size = attachment.get('size')
        name = attachment.get('name')
        url = attachment.get('url')

        content = None
        if url is not None:
            content = requests.get(url, auth=auth)

        attachments.append(dict(name=name, size=size, content_type=content_type,
                            content=content.content))

    print('subject: {}, \nfrom: {}, to: {},\nattachments: {}'.format(
        subject, fromaddr, toaddr, ', '.join([x['name'] for x in attachments])
    ))

    return (topicid, dict(subject=subject, fromaddr=fromaddr, toaddr=toaddr,
            recipients=recipients, body=body_plain, attachments=attachments))


def validate_email_address(addr):
    auth = ('api', MAILGUN_VALIDATION_KEY)
    VALIDATION_API_URL = 'https://api.mailgun.net/v3/address/validate'

    r = requests.get(VALIDATION_API_URL, auth=auth, params={'addresses': addr})
    if r.status_code != 200:
        abort(500, 'error')

    return json.loads(r.text)

def parse_email_address(addr):
    auth = ('api', MAILGUN_VALIDATION_KEY)
    PARSE_API_URL = 'https://api.mailgun.net/v3/address/parse'

    r = requests.get(PARSE_API_URL, auth=auth, params={'addresses': addr})
    if r.status_code != 200:
        abort(500, 'error')

    addrjson = json.loads(r.text)

    addrs = []
    for paddr in addrjson['parsed']:
        fullname, addr = parseaddr(paddr)
        addrs.append(addr)

    if not addrs:
        abort(500, "From adress prase error: {}".format(addr))

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


TYPETALK_API_URL = 'https://typetalk.com/api/v1/topics/'
def post_to_typetalk(topicid, message):
    topicid= 97119
    typetalk_accesstoken = get_typetalk_credential()
    headers = {'Authorization':'Bearer '+ typetalk_accesstoken}

    # upload attachments
    uploaded_filekeys = []
    attachments = message.get('attachments')
    if attachments is not None:
        for a in attachments:
            url = TYPETALK_API_URL + str(topicid) + '/attachments'
            payload = {'file': (a['name'], a['content'], a['content_type'])}
            r = requests.post(url, files=payload, headers=headers)
            if r.status_code == 200:
                uploaded_filekeys.append(json.loads(r.text).get('fileKey'))

    # get or create matome
    addrs = parse_email_address(message.get('fromaddr'))
    from_talkid = None
    if addrs:
        talkname = addrs.pop(0)
        from_talkid = get_or_create_typetalk_matome(typetalk_accesstoken, topicid, talkname)

    addrs = parse_email_address(message.get('toaddr'))
    to_talkid = None
    if addrs:
        local, domain = addrs[0].split('@')
        if domain == 'shiftall.net':
            talkname = local
        to_talkid = get_or_create_typetalk_matome(typetalk_accesstoken, topicid, talkname)

    # post message
    postmsg = 'メールを受信しました。 --- To: {}\n\n'.format(message.get('toaddr'))
    postmsg += 'From: {}\n件名: 「{}」\n'.format(
               message.get('fromaddr'),
               message.get('subject'))

    postmsg += '```\n' + message.get('body') + '\n```\n'

    url = TYPETALK_API_URL + str(topicid)
    payload = {'message': postmsg}
    for i, uf in enumerate(uploaded_filekeys):
        payload['fileKeys[{}]'.format(i)] = uf

    if from_talkid is not None:
        payload['talkIds[0]'] = from_talkid
    if to_talkid is not None:
        payload['talkIds[1]'] = to_talkid

    r = requests.post(url, data=payload, headers=headers)
    if r.status_code != 200:
        abort(500, r.text)
    return r.text

def get_typetalk_credential(scope='topic.read,topic.post,topic.write'):
    url = "https://typetalk.com/oauth2/access_token"
    r = requests.post(url, {'client_id': TYPETALK_CLIENT_ID,
            'client_secret': TYPETALK_CLIENT_SECRET,
            'grant_type': 'client_credentials','scope': scope})
    if r.status_code !=200:
        abort(500, "typetalk api error: status code={}, {}".format(r.status_code, r.text))

    return r.json()['access_token']


def get_or_create_typetalk_matome(typetalk_accesstoken, topicid, name):
    url = TYPETALK_API_URL + str(topicid) + '/talks'
    headers = {'Authorization':'Bearer '+ typetalk_accesstoken}

    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        abort(500, "typetalk api error")

    talksjson = json.loads(r.text)
    for talk in talksjson['talks']:
        if talk['name'] == name:
            return talk['id']

    payload = {'talkName': name}
    r = requests.post(url, payload, headers=headers)
    if r.status_code != 200:
        abort(500, 'typetalk api error')

    talkjson = json.loads(r.text)
    return talkjson['talk']['id']

if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
