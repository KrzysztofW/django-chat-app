{% load static %}{% load i18n %}{% load custom_tags %}{% get_current_language as LANGUAGE_CODE %}
var chatns = {
    general_msg_box : '',
    general_msg_box_hdr : '<div class="contact-profile"><p style="line-height:60px;" id="contact_name_id">&nbsp;&nbsp;{% trans 'Welcome ' %}</p></div><div class="messages" id="inner_msg_box_id"><ul>',
    general_msg_box_footer : '</ul></div>',
    cur_tuid : 'general',
    cur_cuid : '',
    cur_status : 'offline',
    msg_box : document.getElementById('msg_box_id'),
    unread_msg_cnt : new Set(),
    unread_msg_elem : document.getElementById('unread_msgs_id'),

    {% if LANGUAGE_CODE == 'fr' %}
    month : ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    {% else %}
    month : ["Jan.", "Feb.", "March", "April", "May", "June", "July", "August", "Sep.", "Oct.", "Nov.", "Dec." ],
    {% endif %}

    scroll_down_msg_box:function()
    {
	var inner_msg_box = document.getElementById('inner_msg_box_id');

	inner_msg_box.scrollTop = inner_msg_box.scrollHeight;
    },

    truncate_string:function(str, num)
    {
	if (str.length <= num)
	    return str;
	return str.slice(0, num) + '...';
    },

    update_unread_msg_cnt:function(uid, add) {
	if (add)
	    chatns.unread_msg_cnt.add(uid);
	else
	    chatns.unread_msg_cnt.delete(uid);

	if (chatns.unread_msg_cnt.size == 0) {
	    chatns.unread_msg_elem.classList.add('invisible');
	    return;
	}
	chatns.unread_msg_elem.classList.remove('invisible');
    },

    notify_me:function(user_name, uid, img, msg) {
	chatns.play_sound();
	chatns.update_unread_msg_cnt(uid, true);
	if (Notification.permission === 'granted') {
	    var notification = new Notification('{% trans 'Message from' %}' + ' ' + user_name, {
		body: chatns.truncate_string(msg, 40),
	    });
	    notification.onclick = function() {
		var contact_elem = document.getElementById('contact_id_' + uid);

		window.focus();
		chatns.set_active(contact_elem, uid);
		this.close();
	    };
	} else if (Notification.permission !== 'denied') {
	    Notification.requestPermission();
	}
    },

    add_zero:function(i) {
	if (i < 10)
	    i = '0' + i;
	return i;
    },

    get_current_date:function()
    {
	var today = new Date();
	var n = chatns.month[today.getMonth()];
	var h = today.getHours();
	var ampm = '';

	{% if LANGUAGE_CODE == 'en' %}
	if (h > 12) {
	    ampm = ' p.m.';
	    h -= 12;
	} else
	    ampm = ' a.m.';
	return n + ' ' + today.getDate() + ', ' + today.getFullYear() + ', ' + h + ':' + chatns.add_zero(today.getMinutes()) + ampm;
	{% else %}
	return today.getDate() + ' ' + n + ' ' + today.getFullYear() + ' ' + chatns.add_zero(h) + ':' + chatns.add_zero(today.getMinutes());
	{% endif %}
    },

    general_msg_box_show:function()
    {
	chatns.msg_box.innerHTML = chatns.general_msg_box_hdr + chatns.general_msg_box + chatns.general_msg_box_footer;
	chatns.scroll_down_msg_box();
    },

    general_msg_box_update:function(username, img, action)
    {
	chatns.general_msg_box += '<li class="replies"><div><img src="' + img.attr('src') + '"><div class="msg_div"><b>' + username + '</b>&nbsp;' + action + '<span class="msg_span">' + chatns.get_current_date() + '</span></div></div><br></li>';
	if (chatns.cur_tuid == 'general')
	    chatns.general_msg_box_show();
    },

    new_message:function() {
	message = $(".message-input input").val();
	message = message.replace(/<[^>]*>?/gm, '');

	if($.trim(message) == '') {
	    return false;
	}
	if (chatns.cur_tuid == '') {
	    return;
	}

	if (chatns.cur_status == 'offline') {
	    alert('{% trans 'You are offline' %}');
	    return;
	}
	chatns.chat_socket.send(JSON.stringify({
	    'cmd': {{ ws_cmds.MSG.value }},
	    'tuid': chatns.cur_tuid,
	    'msg': encodeURI(message)
	}));
	$('.message-input input').val(null);
    },

    set_active:function(elem, uid)
    {
	$('li').each(function(i) {
	    $(this).removeClass('active');
	});

	elem.classList.add('active');
	chatns.cur_tuid = uid;

	if (uid == 'general') {
	    chatns.general_msg_box_show();
	    return;
	}

	var id = '#user_msg_preview_' + uid;
	var user_msg_preview = $(id);

	if (typeof user_msg_preview.val() !== 'undefined')
	    user_msg_preview.text('');

	$.ajax({
	    url: "{% url 'chat-load-msgs' %}",
	    data: {
		'uid': uid
	    },
	    success: function(data) {
		chatns.msg_box.innerHTML = decodeURI(data);
		chatns.scroll_down_msg_box();
		chatns.update_unread_msg_cnt(uid, false);
	    }
	});
    },

    add_channel:function()
    {
    },

    play_sound:function()
    {
	document.getElementById('sound').play();
    },

    update_status:function(status)
    {
	if (chatns.cur_status == status)
	    return;

	chatns.cur_status = status;

	chatns.chat_socket.send(JSON.stringify({
	    'cmd': {{ ws_cmds.STATUS_UPDATE.value }},
	    'status': status,
	}));
    },
}

chatns.ws_scheme = window.location.protocol === "https:" ? "wss" : "ws";
chatns.chat_socket = new ReconnectingWebSocket(chatns.ws_scheme + '://' +
					       window.location.host +
					       '/ws/chat');

document.addEventListener('DOMContentLoaded', function() {
    if (!Notification) {
	alert('Desktop notifications not available in your browser.');
	return;
    }

    if (Notification.permission !== 'granted')
	Notification.requestPermission();
});

chatns.chat_socket.onopen = function(e) {
    $.ajax({
	url: "{% url 'chat-get-my-status' %}",
	data: {
	    'status': chatns.cur_status
	},
	success: function(data) {
	    if (data['status'] != 'offline') {
		$('#profile-img').removeClass();
		$('#profile-img').addClass(data['status']);
		chatns.cur_status = data['status'];
	    }
	}
    });
}

chatns.chat_socket.onmessage = function(e) {
    var data = JSON.parse(e.data);
    var message = decodeURI(data['message']);
    var cmd = data['cmd'];
    var uid = data['uid'];
    var status = data['status'];

    if (typeof uid === 'undefined' || typeof cmd === 'undefined')
	return;

    if (uid == {{ request.user.id }}) {
	var status_elem = $('#profile-img');
	var user_img = status_elem;
    } else {
	var status_elem = $('#user_id_' + uid);
	var user_img = $('#user_img_' + uid);
    }
    var user_name = $('#user_name_' + uid);

    if (typeof user_name.val() === 'undefined')
	return;
    if (typeof status_elem.val() === 'undefined')
	return;
    if (typeof user_img.val() === 'undefined')
	return;

    switch (cmd) {
    case {{ ws_cmds.DISCONNECT.value }}:
	status_elem.attr('class', 'contact-status offline');
	chatns.general_msg_box_update(user_name.text(), user_img, 'left');
	return;

    case {{ ws_cmds.STATUS_UPDATE.value }}:
	/* update my status */
	if (uid == {{ request.user.id }})
	    chatns.cur_status = status;

	if (status_elem.prop('classList').contains('offline') && status != 'offline')
	    action = 'joined in with status ' + status;
	else if (status == 'offline')
	    action = 'left';
	else if (status == 'online')
	    action = 'is online';
	else
	    action = 'changed status to ' + status;
	status_elem.attr('class', 'contact-status ' + status);
	if (action != 'left' || uid != {{ request.user.id }})
	    chatns.general_msg_box_update(user_name.text(), user_img, action);
	return;
    default:
	break;
    }

    if (chatns.cur_tuid != uid && chatns.cur_tuid != data['reply_tuid']) {
	var user_msg_preview = $('#user_msg_preview_' + uid);

	if (typeof user_msg_preview.val() === 'undefined')
	    return;

	var msg = chatns.truncate_string(message, 80);

	user_msg_preview.text(msg);
	chatns.notify_me(user_name.text(), uid, user_img, msg);
	return;
    }
    if (uid == {{ request.user.id }})
	msg_class = 'sent';
    else {
	if (!document.hasFocus()) {
	    var msg = chatns.truncate_string(message, 80);
	    chatns.notify_me(user_name.text(), uid, user_img, msg);
	}
	msg_class = 'replies';
    }

    $('<li class="' + msg_class + '"><div><img src="' + user_img.attr('src') + '"><div class="msg_div"><b>' + user_name.text() + '</b> <span class="msg_span">' + chatns.get_current_date() + '</span></div></div><br><p class="msg_p">' + message + '</p></li>').appendTo($('.messages ul'));
    $('.message-input input').val(null);
    chatns.scroll_down_msg_box();
};

$("#profile-img").click(function() {
    $("#status-options").toggleClass("active");
});

$(".expand-button").click(function() {
    $("#profile").toggleClass("expanded");
    $("#contacts").toggleClass("expanded");
});

$("#status-options ul li").click(function() {
    $("#profile-img").removeClass();
    $("#status-online").removeClass("active");
    $("#status-away").removeClass("active");
    $("#status-busy").removeClass("active");
    $("#status-offline").removeClass("active");
    $(this).addClass("active");

    if($("#status-online").hasClass("active")) {
	$("#profile-img").addClass("online");
    } else if ($("#status-away").hasClass("active")) {
	$("#profile-img").addClass("away");
    } else if ($("#status-busy").hasClass("active")) {
	$("#profile-img").addClass("busy");
    } else if ($("#status-offline").hasClass("active")) {
	$("#profile-img").addClass("offline");
    } else {
	$("#profile-img").removeClass();
    };

    $("#status-options").removeClass("active");
});

chatns.general_msg_box_show();

$('.submit').click(function() {
    chatns.new_message();
});

$(window).on('keydown', function(e) {
    if (e.which == 13) {
	chatns.new_message();
	return false;
    }
});
