import main
from typetalk_api import TypetalkAPI

url = 'https://se.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjpmYWxzZSwiayI6Ijg3NTQyZmJmLWJhYTctNGRiNy1hZTFlLWIyMmMyZWUwNDY5NyIsInMiOiI2ZTA2MDkzZmM5IiwiYyI6InRhbmtiIn0='
topic_id, message = main.get_message_from_mailgun(url)
TypetalkAPI(topic_id).post_message(message)

