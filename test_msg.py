import main
from typetalk_api import TypetalkAPI

url = 'https://se.api.mailgun.net/v3/domains/mailgun-mx.nonefix.org/messages/eyJwIjpmYWxzZSwiayI6IjY4ODQzYjE2LTZiYTUtNGFmMC05MzQxLWFiMDc0M2Q5N2NmNCIsInMiOiI0NTg1OWQwZTgzIiwiYyI6InRhbmtiIn0='

topic_id, message = main.get_message_from_mailgun(url)

topic_id = 97119
ret = TypetalkAPI(topic_id).post_message(message, url)

post = ret.get('post')
if post is not None:
    post_id = post.get('id')
if post_id is not None:
    main.save_msg_to_cloud_store(message['message_id'], url, post_id)
    print('saved to cloud store')

