import main
from typetalk_api import TypetalkAPI

url = 'https://sw.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjpmYWxzZSwiayI6IjVkYzdlMmE1LWYwNjQtNDAxMC1iOWY1LTgzNTFjOTc4YmQ2OCIsInMiOiI0OGY1MDlkYzAzIiwiYyI6InRhbmtiIn0='

topic_id, message = main.get_message_from_mailgun(url)

topic_id = 97119
TypetalkAPI(topic_id).post_message(message, url)

