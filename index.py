#!/bin/env python2.7
# -*- coding: utf-8 -*-

from flask import *

from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from random import randint

import binascii, os, json
import yaml, requests

from redis_session import RedisSessionInterface

# Load and parse config file
config = yaml.load(file('config.yaml', 'r'))
encrypt = config['encrypt']

app = Flask(__name__, static_url_path='/static')
app.config['recaptcha'] = config['recaptcha']
app.debug = config['debug']
app.session_interface = RedisSessionInterface(config['redis'])

def aesEncrypt(text, secKey):
  pad = 16 - len(text) % 16
  text = text + pad * chr(pad)
  encryptor = AES.new(secKey, 1)
  cipherText = encryptor.encrypt(text)
  cipherText = binascii.b2a_hex(cipherText).upper()
  return cipherText

def encrypted_request(jsonDict):
  jsonStr = json.dumps(jsonDict, separators = (",", ":"))
  encText = aesEncrypt(jsonStr, secretKey)
  data = {
    'eparams': encText,
  }
  return data

nonce = encrypt['nonce']
n, e = int(encrypt["n"], 16), int(encrypt["e"], 16)

def req_netease(url, payload):
  data = encrypted_request(payload)
  r = requests.post(url, data = data, headers = headers)
  result = json.loads(r.text)
  if result['code'] != 200:
    return None
  return result

def req_netease_detail(songId):
  payload = {"method": "POST", "params": {"c": "[{id:%d}]" % songId}, "url": "http://music.163.com/api/v3/song/detail"}
  data = req_netease('http://music.163.com/api/linux/forward', payload)
  if data is None or data['songs'] is None or len(data['songs']) != 1:
    return None
  song =  data['songs'][0]
  return song

def req_netease_url(songId, rate):
  payload = {"method": "POST", "params": {"ids": [songId],"br": rate}, "url": "http://music.163.com/api/song/enhance/player/url"}
  data = req_netease('http://music.163.com/api/linux/forward', payload)
  if data is None or data['data'] is None or len(data['data']) != 1:
    return None
  
  song = data['data'][0]
  if song['code'] != 200 or song['url'] is None:
    return None
  # song['url'] = song['url'].replace('http:', '')
  return song

def req_recaptcha(response, remote_ip):
  r = requests.post('https://www.google.com/recaptcha/api/siteverify', data = {
    'secret': config['recaptcha']['secret'],
    'response': response,
    'remoteip': remote_ip
  });
  result = json.loads(r.text);
  print("req_recaptcha from %s, result: %s" % (remote_ip, r.text))
  return result['success']



print("Generating secretKey for current session...")
secretKey = binascii.a2b_hex(encrypt['secret'])

headers = {
  'Referer': 'http://music.163.com',
  'X-Real-IP': '118.88.88.88',
  'Cookie': 'os=linux; appver=1.0.0.1026; osver=Ubuntu%2016.10',
  'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
}

def sign_request(songId, rate):
  h = SHA256.new()
  h.update(str(songId))
  h.update(str(rate))
  h.update(config["sign_salt"])
  return h.hexdigest()

def is_verified(session):
  if not config['recaptcha']:
    return True
  return 'verified' in session and session['verified'] > 0

def set_verified(session):
  if config['recaptcha']:
    session['verified'] = randint(10, 20)

def decrease_verified(session):
  if config['recaptcha']:
    session['verified'] -= 1;

@app.route("/")
def index():
  verified = is_verified(session)
  return render_template('index.j2', verified = verified)

@app.route("/backdoor")
def backdoor():
  if app.debug:
    set_verified(session)
  return 'ok!'

@app.route('/s/<path:path>')
def static_route(path):
  return app.send_static_file(path)

@app.route("/sign/<int:songId>/<int:rate>", methods=['POST'])
def generate_sign(songId, rate):
  if not is_verified(session):
    # 首先检查谷歌验证
    if 'g-recaptcha-response' not in request.form \
      or not req_recaptcha(
        request.form['g-recaptcha-response'],
        request.headers[config['ip_header']] if config['ip_header'] else request.remote_addr
      ):
      #
      return jsonify({"verified": is_verified(session), "errno": 2})

    set_verified(session)

  # 请求歌曲信息, 然后签个名
  decrease_verified(session)
  song = req_netease_detail(songId)
  if song is None:
    return jsonify({"verified": is_verified(session), "errno": 1})

  return jsonify({
    "verified": True,
    "sign": sign_request(songId, rate),
    "song": {
      "id": song['id'],
      "name": song['name'],
      "artist": [{"id": a['id'], "name": a['name']} for a in song['ar']]
    }
  })

@app.route("/<int:songId>/<int:rate>/<sign>")
def get_song_url(songId, rate, sign):
  if sign_request(songId, rate) != sign:
    return abort(403)

  song = req_netease_url(songId, rate)
  if song is None:
    return abort(404)
  
  response = redirect(song['url'], code=302)
  response.headers["max-age"] = song['expi']
  return response

if __name__ == "__main__":
  print("Running...")
  app.run()
