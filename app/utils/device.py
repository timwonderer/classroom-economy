from flask import request
import re

def is_mobile():
    """
    Returns True if the request comes from a mobile device.
    """
    user_agent = request.headers.get('User-Agent', '').lower()
    return bool(re.search(
        (
            r'android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini'
        ),
        user_agent
    ))
