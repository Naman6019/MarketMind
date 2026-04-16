const chatHistory = document.getElementById('chatHistory');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const processStatus = document.getElementById('processStatus');

// Setup marked.js for Markdown
marked.setOptions({
  gfm: true,
  breaks: true,
});

// Auto-resize textarea
userInput.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = (this.scrollHeight < 120 ? this.scrollHeight : 120) + 'px';
});

// Handle Enter key (Shift+Enter for new line)
userInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

function useSuggestion(text) {
  userInput.value = text;
  sendMessage();
}

async function sendMessage() {
  const text = userInput.value.trim();
  if (!text) return;

  // Add User Message
  appendMessage('user-msg', text);
  userInput.value = '';
  userInput.style.height = 'auto';
  
  // Show processing status
  processStatus.style.display = 'flex';

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text })
    });

    if (!response.ok) {
        throw new Error('Network response was not ok');
    }
    
    const data = await response.json();
    
    // Convert markdown to HTML before appending
    const htmlResponse = marked.parse(data.answer);
    appendHTMLMessage('system-msg', htmlResponse);

  } catch (error) {
    console.error('Error:', error);
    appendHTMLMessage('system-msg', `<p style="color:#ff4d4d">Error: Unable to reach MarketMind core. Make sure the server is running.</p>`);
  } finally {
    processStatus.style.display = 'none';
  }
}

function appendMessage(className, text) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${className}`;
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'msg-content';
  contentDiv.textContent = text;
  
  msgDiv.appendChild(contentDiv);
  chatHistory.appendChild(msgDiv);
  
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

function appendHTMLMessage(className, htmlContent) {
  const msgDiv = document.createElement('div');
  msgDiv.className = `message ${className}`;
  
  const contentDiv = document.createElement('div');
  contentDiv.className = 'msg-content';
  contentDiv.innerHTML = htmlContent;
  
  msgDiv.appendChild(contentDiv);
  chatHistory.appendChild(msgDiv);
  
  chatHistory.scrollTop = chatHistory.scrollHeight;
}
