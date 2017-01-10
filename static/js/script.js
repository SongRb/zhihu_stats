/**
 * Created by Tang Songkai on 1/6/17.
 */


function changeValue(obj) {
    document.getElementById('pagelimit-value').innerHTML = '返回' + String(obj.value) + '条数据';
}

function askForResult() {
    var content = document.getElementById('content').value;

    var para = {querys: [], page: 0};
    if (!document.getElementById('checkbox-question').checked) {
        if (document.getElementById('checkbox-question').checked) {
            para['querys'].push({'type': 'question', 'title': content});
        }

        if (document.getElementById('checkbox-answer').checked) {
            para['querys'].push({'type': 'answer', 'text': content});
        }

        if (document.getElementById('checkbox-user').checked) {
            para['querys'].push({'type': 'user', 'description': content});
        }

        if (document.getElementById('checkbox-article').checked) {
            para['querys'].push({'type': 'article', 'text': content});
        }

        if (document.getElementById('checkbox-topic').checked) {
            para['querys'].push({'type': 'topic', 'text': content});
        }
    }
    else {
        para['querys'].push({'raw': content});
    }

    para['page'] = 1;

    jQuery.ajax({
        url: '/search',
        data: {data: JSON.stringify(para)},
        type: 'POST',
        dataType: 'json',
        success: function (jsonObj) {
            writeResult(jsonObj);
        }
        }
    )
}

function writeResult(jsonObj) {
    jQuery('.search-result').empty();
    jQuery('.suggest-right').empty();
    for (i = 0; i < jsonObj.results.length; i++) {
        var dataList = jsonObj.results[i].data;
        for (j = 0; j < dataList.length; j++) {
            setUpVariousResultSection(dataList[j]);
        }
    }
    jQuery('img').css('max-width', '600');
    var suggestSection = setUpSuggestRightSection('vzch', '一个老司机', '/static/img/home_background-1.png', '轮带逛');
    jQuery('#total-suggest').append(suggestSection);
}

function dateParser(date) {
    var dateStr = String(date);
    return dateStr.substring(0, 4) + '年' + dateStr.substring(4, 6) + '月' + dateStr.substring(6, 8) + '日'
}

function setUpVariousResultSection(dataObj) {
    var resultSection;
    var link;
    var description;
    if (dataObj.type == 'article') {
        link = 'https://zhuanlan.zhihu.com/p/' + String(dataObj.index);
        description = dataObj.likes + ' 赞 ' + dateParser(dataObj.date);
        resultSection = setUpResultSection('文章', dataObj.title, description, dataObj.text, link);
        jQuery('#article-result').append(resultSection);
    }
    else if (dataObj.type == 'question') {
        link = 'https://www.zhihu.com/question/' + String(dataObj.index);
        description = dataObj.tag_indices;
        resultSection = setUpResultSection('问题', dataObj.title, description, dataObj.text, link);
        jQuery('#question-result').append(resultSection);
    }
    else if (dataObj.type == 'answer') {
        link = 'https://www.zhihu.com/answer/' + String(dataObj.index);
        description = dataObj.author_index + dataObj.likes + ' 赞 ' + dateParser(dataObj.date);
        resultSection = setUpResultSection('答案', dataObj.question_index, description, dataObj.text, link);
        jQuery('#answer-result').append(resultSection);
    }
    else if (dataObj.type == 'user') {
        link = 'https://www.zhihu.com/people/' + String(dataObj.index);
        description = '';
        var para = {'type': 'topic', 'index': dataObj.followed_topics};


//                jQuery.ajax({
//                    url: '/search',
//                    data: {data: JSON.stringify(para)},
//                    type: 'POST',
//                    dataType: 'json',
//                    success: function (jsonObj) {
//                        alert(jsonObj);
//                    }
//                });
        resultSection = setUpResultSection('用户', dataObj.alias, description, dataObj.description, link);
        jQuery('#user-result').append(resultSection);
    }
    else if (dataObj.type == 'topic') {
        link = 'https://www.zhihu.com/topic/' + String(dataObj.index);
        description = 'author ' + dataObj.likes + ' 赞 ' + dateParser(dataObj.date);
        resultSection = setUpResultSection('话题', dataObj.contents, description, 000000, link);
        jQuery('#topic-result').append(resultSection);
    }
    jQuery('#total-result').append(resultSection.clone());
}

function setUpResultSection(type, title, description, content, link) {
    return jQuery('<section class="mdl-grid mdl-grid--no-spacing mdl-shadow--2dp section--left " ' +
        'data-transition="slide" style="">' +
        '<div class="mdl-card mdl-cell mdl-cell--12-col">' +
        '<div class="mdl-card__supporting-text"><h4>' +
        type + '：' + title +
        '</h4>' + '<b>' + description + '</b>' + '<br>' +
        content + '<br>' +
        '</div><div class="mdl-card__actions">' +
        '<a href="' + link +
        '" target ="_blank" class="mdl-button" >Show more</a></div></div>' +
        '<button class="mdl-button mdl-js-button mdl-js-ripple-effect mdl-button--icon" id="" onclick="getUrl(this)">' +
        '<i class="material-icons">share</i></button>' +
        '</section>');
}

function setUpSuggestRightSection(title, description, picture, action) {
    var sec = jQuery('<div class="demo-card-square mdl-card mdl-shadow--2dp">' +
        '<div class="mdl-card__title mdl-card--expand"><h2 class="mdl-card__title-text">' +
        title + '</h2> </div> <div class="mdl-card__supporting-text">' +
        description + '</div> <div class="mdl-card__actions mdl-card--border">' +
        '<a class="mdl-button mdl-button--colored mdl-js-button mdl-js-ripple-effect">' + action +
        '</a></div></div>');
    sec.css = ({background: 'url(' + picture + ') bottom right 15% no-repeat #46B6AC'});
    return sec;
}
