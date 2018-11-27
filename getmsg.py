import main
from typetalk_api import TypetalkAPI

url = 'https://se.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjp0cnVlLCJrIjoiMTRiZjY2YWQtOTRmZS00Y2QwLThiZmEtZjQ1ODNjZDk5YWZlIiwicyI6IjYzNGEzYzRjOTgiLCJjIjoidGFua2IifQ=='
topic_id, message = main.get_message_from_mailgun(url)
TypetalkAPI(topic_id).post_message(message)

