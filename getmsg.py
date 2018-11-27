import main

url = 'https://sw.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjpmYWxzZSwiayI6ImRmY2ZjOTFhLTdmMGQtNDE3My04ZmI1LWJmNmRiOGI1Y2NjNiIsInMiOiI5YjQ5YTliMzZmIiwiYyI6InRhbmtiIn0='
topicid, message = main.get_message_from_mailgun(url)
main.post_to_typetalk(topicid, message)
