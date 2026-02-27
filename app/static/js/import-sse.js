/* Shared SSE helpers for import pages */

function terminalAppend(output, icon, text, color) {
    var line = document.createElement('div');
    line.style.color = color || '#d4d4d4';
    line.textContent = icon + ' ' + text;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
}

function readSSE(response, output, onEvent) {
    if (!response.ok) {
        terminalAppend(output, '\u2717', 'Server error: ' + response.status + ' ' + response.statusText, '#f44747');
        return;
    }
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';

    function read() {
        reader.read().then(function(result) {
            if (result.done) return;
            buffer += decoder.decode(result.value, {stream: true});
            var lines = buffer.split('\n');
            buffer = '';
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                if (line.startsWith('data: ')) {
                    try {
                        var event = JSON.parse(line.substring(6));
                        var handled = onEvent(event);
                        if (handled === false) return;
                    } catch (e) { /* incomplete chunk */ }
                } else if (line !== '') {
                    buffer = line;
                }
            }
            read();
        });
    }
    read();
}

function handleSSEEvents(output, modalEl, redirectUrl, startOverBtn) {
    return function(event) {
        if (event.type === 'progress') {
            terminalAppend(output, '\u2192', event.message, '#569cd6');
        } else if (event.type === 'result') {
            terminalAppend(output, '\u2713', event.message, '#6a9955');
        } else if (event.type === 'error') {
            terminalAppend(output, '\u2717', event.message, '#f44747');
        } else if (event.type === 'failed') {
            if (startOverBtn) startOverBtn.style.display = 'inline-block';
            return false;
        } else if (event.type === 'done') {
            terminalAppend(output, '', '', '');
            terminalAppend(output, '\u2714', event.summary, '#dcdcaa');
            terminalAppend(output, '\u2192', 'Redirecting...', '#569cd6');
            var url = typeof redirectUrl === 'function' ? redirectUrl(event) : redirectUrl;
            setTimeout(function() {
                window.location.href = url;
            }, 3000);
            return false;
        }
    };
}
