# [START gae_python37_app]
from flask import Flask
from flask import abort, request

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

import requests

from localenv import *

import typetalk_api
from typetalk_api import TypetalkAPI

@app.route('/')
def hello():
    """Return a friendly HTTP greeting."""
    return 'Hello World!'


@app.route('/recv_email', methods=['POST'])
def recv_email():
    "Receive from mailgun as HTTP request"

    try:
        message_id = request.form.get('Message-Id')
        print('Start processing message: {}'.format(message_id))

        message_url = request.form.get('message-url')
        print('notified message-url: {}'.format(message_url))

        topic_id, message = get_message_from_mailgun(message_url)
        print("received message to Typetalk(topic id:{})".format(topic_id))

        ret = TypetalkAPI(topic_id).post_message(message)
        print("post to typetalk is succeeded: {}".format(str(ret)))
    except Exception as e:
        import traceback
        post_text_to_typetalk(traceback.format_exc(e))

    return 'OK'

def post_text_to_typetalk(text):
    print('post text(simple): {}'.format(text))
    requests.post(TYPETALK_BOT_POST_URL, {'message': text})

def get_message_from_mailgun(message_url):
    "Get message and attachments from Mailgun API"

    auth = ('api', MAILGUN_API_KEY)
    message = requests.get(message_url, auth=auth)
    if message.status_code != 200:
        abort(500, "cannnot get message from mailgun: {}".format(message_url))

    msgjson = message.json()

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

    message_id = msgjson.get('Message-Id')
    in_reply_to = msgjson.get('In-Reply-To')
    references = msgjson.get('References')
    print('Message-ID: {}, In-Reply-To: {}, References: {}'.format(
        message_id, in_reply_to, references
    ))

    # Typetalkのtopicはfromのtypetalk-xxxxのxxxxをidとしてtopicを特定
    topic_id = typetalk_api.get_topic_id_from_toaddr(recipients)
    if topic_id is None:
        abort(500, 'To addr is not valid as topic id: {}'.format(toaddr))
    else:
        print("Target topic id: {}".format(topic_id))

    body = msgjson.get('stripped-text')
    if body is None:
        body = msgjson.get('body-plain')

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

    print('subject: {}\nfrom: {}, to: {}'.format(subject, fromaddr, toaddr))

    if attachments:
        print('attachments: {}'.format(
            ', '.join([x['name'] for x in attachments])
        ))

    return (topic_id, dict(subject=subject, fromaddr=fromaddr, toaddr=toaddr,
            message_id=message_id, in_reply_to=in_reply_to, references=references,
            recipients=recipients, body=body, attachments=attachments))


if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python37_app]
