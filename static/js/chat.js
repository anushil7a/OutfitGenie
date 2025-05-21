document.addEventListener('DOMContentLoaded', function() {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatMessages = document.getElementById('chat-messages');
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

    // Scroll to bottom of chat
    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Add message to chat
    function addMessage(message, isUser = true) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start space-x-3';
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'flex-shrink-0';
        
        const avatar = document.createElement('div');
        avatar.className = isUser ? 'w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-white' : 'w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white';
        avatar.textContent = isUser ? 'You' : 'AI';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1 bg-gray-100 rounded-lg p-4';
        
        const messageText = document.createElement('p');
        messageText.className = 'text-gray-800';
        messageText.textContent = message;
        
        avatarDiv.appendChild(avatar);
        contentDiv.appendChild(messageText);
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // Add AI response with images
    function addAIResponse(response, imageUrls = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start space-x-3';
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'flex-shrink-0';
        
        const avatar = document.createElement('div');
        avatar.className = 'w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white';
        avatar.textContent = 'AI';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1 bg-gray-100 rounded-lg p-4';
        
        const messageText = document.createElement('p');
        messageText.className = 'text-gray-800';
        messageText.textContent = response;
        
        avatarDiv.appendChild(avatar);
        contentDiv.appendChild(messageText);

        // Add images if available
        if (imageUrls && imageUrls.length > 0) {
            const imageGrid = document.createElement('div');
            imageGrid.className = 'mt-4 grid grid-cols-2 gap-4';
            
            imageUrls.forEach(url => {
                const imgContainer = document.createElement('div');
                imgContainer.className = 'relative';
                
                const img = document.createElement('img');
                img.src = url;
                img.alt = 'Recommended outfit';
                img.className = 'w-full h-48 object-cover rounded-lg';
                
                imgContainer.appendChild(img);
                imageGrid.appendChild(imgContainer);
            });
            
            contentDiv.appendChild(imageGrid);
        }
        
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
        scrollToBottom();
    }

    // Handle form submission
    chatForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = messageInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        addMessage(message);
        messageInput.value = '';
        
        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ message })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Add AI response with images
                addAIResponse(data.response, data.image_urls);
            } else {
                addMessage('Sorry, I encountered an error. Please try again.', false);
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('Sorry, I encountered an error. Please try again.', false);
        }
    });

    // Initial scroll to bottom
    scrollToBottom();
}); 