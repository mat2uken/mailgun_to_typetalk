import main

url = 'https://sw.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjpmYWxzZSwiayI6IjJhZGY3MjQ1LTc3MDYtNGFiYy04NjYzLTE4YzFiNThkNzVhYiIsInMiOiJiZjgwNDA4ZTU2IiwiYyI6InRhbmtiIn0='
topicid, message = main.get_message_from_mailgun(url)
main.post_to_typetalk(topicid, message)
