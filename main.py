# [START gae_python37_app]
from flask import Flask, Response
from flask import abort, request

# If `entrypoint` is not defined in app.yaml, App Engine will look for an app
# called `app` in `main.py`.
app = Flask(__name__)

import requests

from localenv import *

import typetalk_api
from typetalk_api import TypetalkAPI, MessageStore

@app.route('/')
def hello():
    """Return a friendly HTTP greeting."""
    return 'Hello World!'


@app.route('/recv_email', methods=['POST'])
def recv_email():
    "Receive from mailgun as HTTP request"

    message_id = None
    message_url = None
    try:
        message_id = request.form.get('Message-Id')
        print('Start processing message: {}'.format(message_id))

        message_url = request.form.get('message-url')
        print('notified message-url: {}'.format(message_url))

        topic_id, message = get_message_from_mailgun(message_url)
        print("received message to Typetalk(topic id:{})".format(topic_id))


        ret = TypetalkAPI(topic_id).post_message(message, message_url=message_url)
        print("post to typetalk is succeeded: {}".format(str(ret)))

        post = ret.get('post')
        if post is not None:
            post_id = post.get('id')
        if post_id is not None:
            save_msg_to_cloud_store(message_id, message_url, post_id)
            print('saved to cloud store: {}'.format(message_id))
    except Exception as e:
        import traceback
        exception_msg = traceback.format_exc()
        post_text_to_typetalk(message_id, message_url, exception_msg)
        abort(500, exception_msg)

    return 'OK'


@app.route('/view_message', methods=['GET'])
def view_message():
    message_id = request.args.get('message_id')

    ms = MessageStore()
    message_entity = ms.get_entity(message_id)
    message_url = message_entity['msg_url']

    print('mailgun msg url: {}'.format(message_url))

    auth = ('api', MAILGUN_API_KEY)
    r = requests.get(message_url, auth=auth)
    if r.status_code != 200:
        abort(404, 'message is not found: {}'.format(r.text))
    return Response(r.json().get('body-plain'), mimetype='text/plain')


def save_msg_to_cloud_store(message_id, message_url, post_id):
    ms = MessageStore()
    return ms.save(message_id, message_url, post_id)


def post_text_to_typetalk(message_id, message_url, text):
    print('message id: {}, url: {}'.format(message_id, message_url))
    print('post text(simple): {}'.format(text))

    msg = '''Message-ID: {}\nMessage-URL : {}\n{}'''.format(message_id, message_url, text)
    requests.post(TYPETALK_BOT_POST_URL, {'message': msg})


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
        print('got attachment: name={}, size={}'.format(name, size))

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
