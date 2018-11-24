import main

url = 'https://sw.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjpmYWxzZSwiayI6IjNkZWZkOGM5LWRjY2ItNDExZi05YzY3LWJhNWU4ZTM5ZGI3MCIsInMiOiIxNmYyOTNkZDk5IiwiYyI6InRhbmtiIn0='
topicid, message = main.get_message_from_mailgun(url)
main.post_to_typetalk(topicid, message)
