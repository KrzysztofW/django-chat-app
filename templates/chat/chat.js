{% load static %}{% load i18n %}{% load custom_tags %}{% get_current_language as LANGUAGE_CODE %}
var chat_settings = {
    notifs_mp : {{ settings.notifs_mp }},
    notifs_chann : {{ settings.notifs_chann }},
    notifs_sound : {{ settings.notifs_sound }},
    notifs_sound_chann : {{ settings.notifs_sound_chann }},
}
var chatns = {
    general_msg_box : '',
    general_msg_box_hdr : '<div class="contact-profile"><p style="line-height:60px;" id="contact_name_id">&nbsp;&nbsp;{% trans 'Welcome ' %}</p></div><div class="messages" id="inner_msg_box_id"><ul>',
    general_msg_box_footer : '</ul></div>',
    cur_tuid : 'general',
    cur_status : 'offline',
    msg_box : document.getElementById('msg_box_id'),
    unread_msg_cnt : new Set(),
    unread_msg_elem : document.getElementById('unread_msgs_id'),
    unread_msg_tim : 0,
    has_focus : true,
    scroll_no_focus_cnt : 0,

    {% if LANGUAGE_CODE == 'fr' %}
    month : ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    {% else %}
    month : ["Jan.", "Feb.", "March", "April", "May", "June", "July", "August", "Sep.", "Oct.", "Nov.", "Dec." ],
    {% endif %}

    scroll_down_msg_box:function(val)
    {
	var inner_msg_box = document.getElementById('inner_msg_box_id');

	inner_msg_box.scrollTop = inner_msg_box.scrollHeight - val;
    },
    scroll_up_msg_box:function(val)
    {
	var inner_msg_box = document.getElementById('inner_msg_box_id');

	inner_msg_box.scrollTop = val;
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

    unread_msg_cur_user_clear_cb:function() {
	chatns.update_unread_msg_cnt(chatns.cur_tuid, false);
	chatns.unread_msg_tim = 0;
    },
    unread_msg_cur_user_clear:function() {
	if (chatns.unread_msg_tim || chatns.unread_msg_cnt.size == 0)
	    return;

	chatns.has_focus = true;
	chatns.scroll_no_focus_cnt = 0;
	chatns.unread_msg_tim = setTimeout(chatns.unread_msg_cur_user_clear_cb, 3000);
    },

    notify_me:function(user_name, uid, is_channel, img, msg) {
	if ((is_channel && chat_settings.notifs_sound_chann) ||
	    (!is_channel && chat_settings.notifs_sound))
	    chatns.play_sound();

	chatns.update_unread_msg_cnt(uid, true);
	if (Notification.permission === 'granted') {
	    if (is_channel && !chat_settings.notifs_chann)
		return;
	    if (!is_channel && !chat_settings.notifs_mp)
		return;
	    var notification = new Notification('{% trans 'Message from' %}' + ' ' + user_name, {
		body: chatns.truncate_string(msg, 40),
	    });
	    notification.onclick = function() {
		var contact_elem = document.getElementById('contact_id_' + uid);

		window.focus();
		chatns.set_active(contact_elem, uid, is_channel);
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
	chatns.scroll_down_msg_box(0);
    },

    general_msg_box_update:function(username, img, action)
    {
	chatns.general_msg_box += '<li class="replies"><div><img src="' + img.attr('src') + '"><div class="msg_div"><b>' + username + '</b>&nbsp;' + action + '<span class="msg_span">' + chatns.get_current_date() + '</span></div></div><br></li>';
	if (chatns.cur_tuid == 'general')
	    chatns.general_msg_box_show();
    },

    new_message:function() {
	var is_channel = false;
	var tuid = chatns.cur_tuid;

	message = $(".message-input input").val();
	message = message.replace(/<[^>]*>?/gm, '');

	if ($.trim(message) == '' || chatns.cur_tuid == '')
	    return;

	if (chatns.cur_status == 'offline') {
	    alert("{% trans 'You are offline' %}");
	    return;
	}
	if (typeof tuid == 'string' && tuid.includes('channel_')) {
	    is_channel = true;
	    tuid = tuid.replace('channel_', '');
	}
	chatns.chat_socket.send(JSON.stringify({
	    'cmd': {{ ws_cmds.MSG.value }},
	    'tuid': tuid,
	    'msg': encodeURI(message),
	    'is_channel' : is_channel
	}));
	$('.message-input input').val(null);
    },

    msg_pos : 0,

    set_active:function(elem, uid, is_channel)
    {
	if (elem.classList.contains('active'))
	    return;

	$('li').each(function(i) {
	    $(this).removeClass('active');
	});

	elem.classList.add('active');
	if (is_channel) {
	    var name = '#channel_' + uid;
	    chatns.cur_tuid = 'channel_' + uid;
	} else {
	    var name = '#user_name_' + uid;
	    chatns.cur_tuid = uid;
	}

	if (uid == 'general') {
	    chatns.general_msg_box_show();
	    return;
	}

	name = $(name);

	if (typeof name.val() !== 'undefined')
	    name.removeClass('username_unread_msg');

	chatns.msg_pos = 0;
	$.ajax({
	    url: "{% url 'chat-load-msgs' %}",
	    data: {
		'uid': uid,
		'is_channel' : is_channel,
		'pos': chatns.msg_pos,
	    },
	    success: function(data) {
		chatns.msg_box.innerHTML = decodeURI(data);
		chatns.scroll_down_msg_box(0);
		if (is_channel)
		    uid = 'channel_' + uid;
		chatns.update_unread_msg_cnt(uid, false);
		chatns.msg_pos += {{ msg_limit }};
	    }
	});
    },

    settings_show:function()
    {
	var settings = document.getElementById('settings_box_id');

	settings.classList.remove('invisible');
    },
    settings_close_win:function()
    {
	var settings = document.getElementById('settings_box_id');

	settings.classList.add('invisible');
    },
    settings_set_error:function(error)
    {
	var error_elem = document.getElementById('settings_error_id');
	var error_div = document.getElementById('settings_error_div');

	if (error)
	    error_elem.classList.remove('invisible');
	else
	    error_elem.classList.add('invisible');
	error_div.innerHTML = '<strong>' + error + '</strong>';
    },
    settings_save:function()
    {
	var notifs_mp = document.getElementById('notifs_mp_id');
	var notifs_chann = document.getElementById('notifs_chann_id');
	var notifs_sound = document.getElementById('notifs_sound_mp_id');
	var notifs_sound_chann = document.getElementById('notifs_sound_chann_id');
	var settings = document.getElementById('settings_box_id');

	$.ajax({
	    url: "{% url 'chat-set-settings' %}",
	    data: {
		'mp': notifs_mp.checked ? 1 : 0,
		'chann': notifs_chann.checked ? 1 : 0,
		'sound': notifs_sound.checked ? 1 : 0,
		'sound_chann': notifs_sound_chann.checked ? 1 : 0
	    },
	    success: function() {
		val = notifs_mp.checked ? 1 : 0;
		chat_settings.notifs_mp = val

		val = notifs_chann.checked ? 1 : 0;
		chat_settings.notifs_chann = val;

		val = notifs_sound.checked ? 1 : 0;
		chat_settings.notifs_sound = val;

		val = notifs_sound_chann.checked ? 1 : 0;
		chat_settings.notifs_sound_chann = val;

		settings.classList.add('invisible');
	    },
	    error: function() {
		chatns.settings_set_error("{% trans 'Cannot save settings' %}");
	    }
	});

	return false;
    },
    channel_close_win:function()
    {
	var channel_box = document.getElementById('channel_box_id');

	channel_box.classList.add('invisible');
	return false;
    },

    add_channel_set_error:function(error)
    {
	var error_elem = document.getElementById('add_channel_error_id');
	var channel_name = document.getElementById('add_channel_id');
	var error_div = document.getElementById('add_channel_error_div');

	if (error) {
	    error_elem.classList.remove('invisible');
	    channel_name.classList.add('is-invalid');
	} else {
	    error_elem.classList.add('invisible');
	    channel_name.classList.remove('is-invalid');
	}
	error_div.innerHTML = '<strong>' + error + '</strong>';

    },
    add_channel_to_my_list:function(id, name)
    {
	$('<input type="hidden" id="channel_name_' + id + '" value="' + name +'"><li id="contact_id_channel_' + id + '" class="contact" onclick="chatns.set_active(this, ' + id + ', true)" style="padding:10px;" onmouseover="chatns.channel_remove_btn(this, ' + id + ', false);" onmouseout="chatns.channel_remove_btn(this, ' + id + ',true);"><div class="wrap"><div class="meta"><i class="fas fa-hashtag fa-2x" style="margin:-5px;"></i><div style="margin:-23px 0 0 45px;font-weight:bold;" id="channel_' + id + '">' + name + '<div style="display:none;">&nbsp; <a href="" onclick="return chatns.remove_channel(' + id + ');"><i class="fas fa-minus-circle"></i></a></div></div></div></div></li>').insertAfter($('#contact_id_general'));
    },
    add_channel_close_win:function()
    {
	var channel_box = document.getElementById('channel_box_id');
	var channel_name = document.getElementById('add_channel_id');

	$.ajax({
	    url: "{% url 'chat-add-channel' %}",
	    data: {
		'name': add_channel_id.value,
	    },
	    success: function(d) {
		var general_li = document.getElementById('contact_id_general');

		if (d['err']) {
		    chatns.add_channel_set_error(d['err']);
		    return;
		}
		channel_box.classList.add('invisible');
		chatns.add_channel_to_my_list(d['id'], add_channel_id.value);
		add_channel_id.value = '';
	    },
	    error: function() {
		chatns.add_channel_set_error("{% trans 'Cannot add channel' %}");
	    }
	});

	return false;
    },
    join_channel:function(id, name)
    {
	$.ajax({
	    url: "{% url 'chat-join-channel' %}",
	    data: {
		'id': id
	    },
	    success: function() {
		var channel_box = document.getElementById('channel_box_id');

		channel_box.classList.add('invisible');
		chatns.add_channel_to_my_list(id, name);
		add_channel_id.value = '';
	    },
	    error: function() {
		chatns.add_channel_set_error("{% trans 'Cannot join channel' %}");
	    }
	});

	return false;
    },
    channel_remove_btn:function(item, id, remove)
    {
	if (chatns.cur_tuid != 'channel_' + id)
	    return;
	if (remove) {
	    chatns.add_channel_set_error();
	    style = 'display:none';
	} else {
	    style = 'display:inline';
	}
	item.children[0].children[0].children[1].children[0].style = style;

    },
    remove_channel:function(id)
    {
	if (!confirm("{% trans 'Are you sure to remove the channel?' %}"))
	    return false;

	$.ajax({
	    url: "{% url 'chat-remove-channel' %}",
	    data: {
		'id': id
	    },
	    success: function(d) {
		document.getElementById('contact_id_channel_' + id).remove();
		chatns.set_active(document.getElementById('contact_id_general'), 'general', false);
	    },
	});
	return false;
    },
    add_channel:function()
    {
	var channel_box = document.getElementById('channel_box_id');
	var other_channels = document.getElementById('other_channels_id');

	other_channels.innerHTML = "{% trans 'loading...' %}";
	chatns.add_channel_set_error();

	$.ajax({
	    url: "{% url 'chat-list-channels' %}",
	    success: function(data) {
		other_channels.innerHTML = data;
		other_channels.classList.remove('username_unread_msg');
	    },
	    error: function() {
		other_channels.innerHTML = "{% trans 'cannot get channel list' %}";
		other_channels.classList.add('username_unread_msg');
	    },
	});

	channel_box.classList.remove('invisible');
    },

    chat_insert_msg:function(msg_class, user_img, user_name, message)
    {
	$('<li class="' + msg_class + '"><div><img src="' + user_img + '"><div class="msg_div"><b>' + user_name + '</b> <span class="msg_span">' + chatns.get_current_date() + '</span></div></div><br><p class="msg_p">' + message + '</p></li>').appendTo($('.messages ul'));
	$('.message-input input').val(null);

	if (chatns.has_focus || msg_class == 'sent') {
	    chatns.scroll_down_msg_box(0);
	    chatns.scroll_no_focus_cnt = 0;
	}
	else if (chatns.scroll_no_focus_cnt <= 420) {
	    chatns.scroll_down_msg_box(chatns.scroll_no_focus_cnt);
	    chatns.scroll_no_focus_cnt += 420;
	}
    },
    chat_handle_channel_msg:function(uid, user_name, user_image, cid, message)
    {
	var msg = chatns.truncate_string(message, 80);
	var chann_cid = 'channel_' + cid;

	if (chatns.cur_tuid != chann_cid) {
	    var channel_elem = $('#channel_' + cid);

	    if (typeof channel_elem.val() === 'undefined')
		return;

	    channel_elem.addClass('username_unread_msg');
	    if (uid != {{ request.user.id }})
		chatns.notify_me(user_name, chann_cid, true, '', msg);
	    return;
	}
	if (uid != {{ request.user.id }}) {
	    if (!chatns.has_focus)
		chatns.notify_me(user_name, chann_cid, true, '', msg);
	    var direction = 'replies';
	} else {
	    var direction = 'sent';
	}
	chatns.chat_insert_msg(direction, user_image, user_name, message);
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

    msg_box_loading : false,

    msg_box_onscroll:function(elem)
    {
	if (chatns.msg_box_loading)
	    return;

	if (elem.scrollTop != 0)
	    return;

	var loading = document.getElementById('loading_id');

	chatns.msg_box_loading = true;
	loading.classList.remove('invisible');

	if (typeof chatns.cur_tuid == 'string' && chatns.cur_tuid.includes('channel_')) {
	    is_channel = true;
	    tuid = chatns.cur_tuid.replace('channel_', '');
	} else {
	    is_channel = false;
	    tuid = chatns.cur_tuid;
	}

	$.ajax({
	    url: "{% url 'chat-load-msgs' %}",
	    data: {
		'uid': tuid,
		'pos': chatns.msg_pos,
		'load': 1,
		'is_channel' : is_channel
	    },
	    success: function(data) {
		var inner_msg_box = document.getElementById('inner_msg_box_id');
		var mbox = inner_msg_box.children[1];
		var hidden_cur_msg_box = document.getElementById('hidden_cur_msg_box_id');
		var data = decodeURI(data);

		hidden_cur_msg_box.firstElementChild.innerHTML = data;

		mbox.innerHTML = data + mbox.innerHTML;
		chatns.msg_pos += {{ msg_limit }};
		chatns.msg_box_loading = false;

		/* set scrolling position */
		var pos = hidden_cur_msg_box.clientHeight;

		if (pos > 500)
		    pos += 500;

		if (data.length > 5)
		    chatns.scroll_up_msg_box(pos);

		loading.classList.add('invisible');
	    },
	    error: function() {
		chatns.msg_box_loading = false;
	    }
	});
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
    var is_channel = data['is_channel'];

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

    if (is_channel) {
	var cid = data['cid'];

	if (typeof cid == 'undefined' || cmd != {{ ws_cmds.MSG.value }})
	    return;
	return chatns.chat_handle_channel_msg(uid, user_name.text(),
					      user_img.attr('src'), cid,
					      message);
    }

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
    case {{ ws_cmds.NEW_MSGS.value }}:
	var uids = JSON.parse(data['uids_msgs']);
	var u_prefix = 'user_name_';
	var c_prefix = 'channel_';

	if (uids.length)
	    chatns.unread_msg_elem.classList.remove('invisible');

	for (i = 0; i < uids.length; i++) {
	    var uid = uids[i][0];
	    var is_channel = uids[i][1];
	    if (is_channel)
		var name = c_prefix + uid;
	    else
		var name = u_prefix + uid;
	    var elem = document.getElementById(name);

	    if (typeof elem === 'undefined')
		continue;
	    elem.classList.add('username_unread_msg');

	    if (chatns.cur_tuid != uid)
		chatns.update_unread_msg_cnt(name, true);
	}
	return;
    default:
	break;
    }

    if (chatns.cur_tuid != uid && chatns.cur_tuid != data['reply_tuid']) {
	var username = $('#user_name_' + uid);

	if (typeof username.val() === 'undefined')
	    return;

	var msg = chatns.truncate_string(message, 80);

	username.addClass('username_unread_msg');
	chatns.notify_me(user_name.text(), uid, false, user_img, msg);
	return;
    }
    if (uid == {{ request.user.id }})
	msg_class = 'sent';
    else {
	if (!chatns.has_focus) {
	    var msg = chatns.truncate_string(message, 80);
	    chatns.notify_me(user_name.text(), uid, false, user_img, msg);
	}
	msg_class = 'replies';
    }

    chatns.chat_insert_msg(msg_class, user_img.attr('src'), user_name.text(), message);
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

if (Notification.permission !== 'denied') {
    Notification.requestPermission();
}
