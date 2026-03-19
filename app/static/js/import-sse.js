/* Shared SSE helpers for import pages — 9600 baud terminal style */

var BAUD_CPS = 120; // ~1200 baud feel — visible typewriter on modern displays
var _cursor = null;
var _typeRAF = null;
var _typeQueue = [];
var _currentTyping = null; // { textNode, fullText }

function _getCursor() {
    if (!_cursor) {
        _cursor = document.createElement('span');
        _cursor.className = 'terminal-cursor blinking';
        _cursor.style.position = 'relative';
        var block = document.createElement('span');
        block.className = 'cursor-block';
        block.textContent = '\u2588';
        var under = document.createElement('span');
        under.className = 'cursor-under';
        under.textContent = '_';
        _cursor.appendChild(block);
        _cursor.appendChild(under);
    }
    return _cursor;
}

function _moveCursor(parent, blinking) {
    var cursor = _getCursor();
    if (cursor.parentNode) cursor.remove();
    cursor.classList.toggle('blinking', blinking);
    parent.appendChild(cursor);
}

function _flushAll(output) {
    if (_typeRAF) {
        cancelAnimationFrame(_typeRAF);
        _typeRAF = null;
    }
    if (_currentTyping) {
        _currentTyping.textNode.textContent = _currentTyping.fullText;
        _currentTyping = null;
    }
    while (_typeQueue.length > 0) {
        var item = _typeQueue.shift();
        var line = document.createElement('div');
        line.style.color = item.color || '#d4d4d4';
        line.textContent = item.fullText;
        item.output.appendChild(line);
    }
    if (output) output.scrollTop = output.scrollHeight;
}

function _removeCursor(output) {
    _flushAll(output);
    var cursor = _getCursor();
    if (cursor.parentNode) cursor.remove();
}

function _typeNextLine() {
    if (_typeQueue.length === 0) return;

    var item = _typeQueue.shift();
    var output = item.output;
    var fullText = item.fullText;
    var color = item.color;

    var line = document.createElement('div');
    line.style.color = color || '#d4d4d4';

    if (!fullText.trim()) {
        line.innerHTML = '&nbsp;';
        output.appendChild(line);
        _moveCursor(line, true);
        output.scrollTop = output.scrollHeight;
        _typeNextLine();
        return;
    }

    var textNode = document.createTextNode('');
    line.appendChild(textNode);
    output.appendChild(line);
    _moveCursor(line, false); // solid cursor while typing

    _currentTyping = { textNode: textNode, fullText: fullText };

    var startTime = null;
    function frame(timestamp) {
        if (!startTime) startTime = timestamp;
        var elapsed = timestamp - startTime;
        var chars = Math.min(Math.floor(elapsed * BAUD_CPS / 1000), fullText.length);
        textNode.textContent = fullText.substring(0, chars);
        output.scrollTop = output.scrollHeight;

        if (chars < fullText.length) {
            _typeRAF = requestAnimationFrame(frame);
        } else {
            _typeRAF = null;
            _currentTyping = null;
            _moveCursor(line, true); // blink when idle
            _typeNextLine();
        }
    }
    _typeRAF = requestAnimationFrame(frame);
}

function terminalAppend(output, icon, text, color) {
    var prefix = icon ? icon + ' ' : '';
    var fullText = prefix + text;
    _typeQueue.push({ output: output, fullText: fullText, color: color });
    if (!_typeRAF && !_currentTyping) {
        _typeNextLine();
    }
}

function readSSE(response, output, onEvent, onStreamEnd) {
    if (!response.ok) {
        terminalAppend(output, '\u2717', 'Server error: ' + response.status + ' ' + response.statusText, '#f44747');
        if (onStreamEnd) onStreamEnd();
        return;
    }

    // Show blinking cursor while waiting for first event
    _moveCursor(output, true);

    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';

    function read() {
        reader.read().then(function(result) {
            if (result.done) {
                _removeCursor(output);
                if (onStreamEnd) onStreamEnd();
                return;
            }
            buffer += decoder.decode(result.value, {stream: true});
            var lines = buffer.split('\n');
            buffer = lines.pop();  // preserve incomplete trailing line
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].trim();  // handle \r\n
                if (line.startsWith('data: ')) {
                    try {
                        var event = JSON.parse(line.substring(6));
                        var handled = onEvent(event);
                        if (handled === false) return;
                    } catch (e) { /* malformed JSON */ }
                }
            }
            read();
        }).catch(function(err) {
            _removeCursor(output);
            terminalAppend(output, '\u2717', 'Connection error: ' + err.message, '#f44747');
            if (onStreamEnd) onStreamEnd();
        });
    }
    read();
}

function handleSSEEvents(output, modalEl, redirectUrl, startOverBtn) {
    var receivedTerminal = false;

    return {
        onEvent: function(event) {
            if (event.type === 'progress') {
                terminalAppend(output, '\u2192', event.message, '#569cd6');
            } else if (event.type === 'result') {
                terminalAppend(output, '\u2713', event.message, '#6a9955');
            } else if (event.type === 'error') {
                terminalAppend(output, '\u2717', event.message, '#f44747');
            } else if (event.type === 'failed') {
                receivedTerminal = true;
                _removeCursor(output);
                if (startOverBtn) startOverBtn.style.display = 'inline-block';
                return false;
            } else if (event.type === 'done') {
                receivedTerminal = true;
                terminalAppend(output, '', '', '');
                terminalAppend(output, '\u2714', event.summary, '#dcdcaa');
                terminalAppend(output, '\u2192', 'Redirecting...', '#569cd6');
                var url = typeof redirectUrl === 'function' ? redirectUrl(event) : redirectUrl;
                setTimeout(function() {
                    window.location.href = url;
                }, 3000);
                return false;
            }
        },
        onStreamEnd: function() {
            if (!receivedTerminal) {
                terminalAppend(output, '\u2717', 'Connection to server was lost. Please try again.', '#f44747');
                if (startOverBtn) startOverBtn.style.display = 'inline-block';
            }
        }
    };
}
