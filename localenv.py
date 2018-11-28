# coding: utf-8

import os

VIEW_MESSAGE_CONTINUE_URL = 'https://typetalktools.appspot.com/view_message'

MAILGUN_DOMAIN = 'mailgun-mx.nonefix.org'

MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
MAILGUN_VALIDATION_KEY = os.environ.get('MAILGUN_VALIDATION_KEY')
TYPETALK_CLIENT_ID = os.environ.get('TYPETALK_CLIENT_ID')
TYPETALK_CLIENT_SECRET = os.environ.get('TYPETALK_CLIENT_SECRET')
TYPETALK_BOT_POST_URL = os.environ.get('TYPETALK_BOT_POST_URL')

if os.environ.get('GAE_ENV') != 'standard':
    import yaml
    data = yaml.load(open('secret.yaml'))
    env = data['env_variables']
    MAILGUN_API_KEY = env['MAILGUN_API_KEY']
    MAILGUN_VALIDATION_KEY = env['MAILGUN_VALIDATION_KEY']
    TYPETALK_CLIENT_ID = env['TYPETALK_CLIENT_ID']
    TYPETALK_CLIENT_SECRET = env['TYPETALK_CLIENT_SECRET']
    TYPETALK_BOT_POST_URL = env['TYPETALK_BOT_POST_URL']

print('MAILGUN_API_KEY: {}'.format(MAILGUN_API_KEY))
print('MAILGUN_VALIDATION_KEY: {}'.format(MAILGUN_VALIDATION_KEY))
print('TYPETALK_CLIENT_ID: {}'.format(TYPETALK_CLIENT_ID))
print('TYPETALK_CLIENT_SECRET: {}'.format(TYPETALK_CLIENT_SECRET))
print('TYPETALK_BOT_POST_URL: {}'.format(TYPETALK_BOT_POST_URL))


