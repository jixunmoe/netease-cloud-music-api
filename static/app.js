document.body.classList.remove('nojs');
document.body.classList.add('js');
$(function () {
  var $body = $('body');
  var base = location.protocol + '//' + location.host + '/';
  var errors = ['', '音乐数据解析失败'];
  var preview = document.getElementById('preview');

  var app = new Vue({
    el: '#app',
    data: {
      verified: $body.data('verified'),
      error: '',

      src_url: '',
      rate: 128000,

      url: '',
      song: {}
    },
    methods: {
      sign: function (e) {
        e.preventDefault();
        app.url = '';
        var data = $('#sign', app.$el).serialize();
        var songId = app.src_url;
        if (!/^\d+$/.test(songId)) {
          var m = songId.match(/song\?id=(\d+)/);
          if (m && m.length > 0) {
            songId = m[1];
          } else {
            app.error = "无效的 ID 或无法识别的地址。";
            return ;
          }
        }

        var param = songId + '/' + app.rate;

        $.post('/sign/' + param, data, function (response) {
          app.verified = response.verified;
          if (!response.verified) {
            app.error = '请先填写验证码!';
            loadCaptcha();
            return ;
          }

          if (response.errno) {
            app.error = errors[response.errno];
            return ;
          }

          app.url = base + param + '/' + response.sign;
          app.song = response.song;
        }).fail(function () {
          app.error = "服务器内部错误。";
        });
      }
    },
    created: function () {
      document.body.classList.add('vue');
      if (!this.verified) {
        loadCaptcha();
      }
    }
  });

  function loadCaptcha () {
    if (window.grecaptcha) {
      grecaptcha.render('recaptcha', {
        'sitekey': $body.data('sitekey')
      });
    } else {
      var script = document.createElement('script');
      script.src = 'https://www.google.com/recaptcha/api.js?onload=loadCaptcha&render=explicit';
      document.body.appendChild(script);
    }
  }

  window.loadCaptcha = loadCaptcha;
  window.app = app;
});