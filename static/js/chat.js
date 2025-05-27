document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatMessages = document.getElementById('chat-messages');
    const chatHistory = document.getElementById('chat-history');
    const recommendationMode = document.getElementById('recommendation-mode');
    const modeLabel = document.getElementById('mode-label');
    let currentChatId = null;

    // Update mode label based on toggle state
    function updateModeLabel() {
        if (recommendationMode.checked) {
            modeLabel.textContent = 'Recommend from my wardrobe only';
            modeLabel.classList.remove('text-gray-700');
            modeLabel.classList.add('text-indigo-600', 'font-semibold');
        } else {
            modeLabel.textContent = 'Recommend from all clothes';
            modeLabel.classList.remove('text-indigo-600', 'font-semibold');
            modeLabel.classList.add('text-gray-700');
        }
    }

    // Add toggle switch event listener
    recommendationMode.addEventListener('change', updateModeLabel);

    // Add welcome message
    addMessage('AI', 'Hi! I\'m your AI Fashion Assistant. I can help you create perfect outfits using your uploaded clothes. You can ask me things like:', true);
    addMessage('AI', '• "What should I wear for a casual dinner?"\n• "Can you suggest an outfit for a job interview?"\n• "What goes well with my blue shirt?"\n• "Help me create a summer outfit"', true);

    // Load chat history
    loadChatHistory();

    // Handle form submission
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage('You', message);
        messageInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({ 
                    message,
                    chat_id: currentChatId,  // Include current chat ID if it exists
                    wardrobe_only: recommendationMode.checked  // Include recommendation mode
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                // Update current chat ID
                currentChatId = data.chat_id;
                
                // Add AI response to chat
                addMessage('AI', data.response, true);
                
                // If there are recommended images, display them
                if (data.image_urls && data.image_urls.length > 0) {
                    const imageContainer = document.createElement('div');
                    imageContainer.className = 'mt-4 grid grid-cols-2 gap-4';
                    data.image_urls.forEach(url => {
                        const img = document.createElement('img');
                        img.src = url;
                        img.className = 'w-full h-48 object-cover rounded-lg';
                        imageContainer.appendChild(img);
                    });
                    chatMessages.appendChild(imageContainer);
                }

                // Update chat history
                loadChatHistory();
            } else {
                addMessage('AI', 'Sorry, I encountered an error. Please try again.', true);
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('AI', 'Sorry, I encountered an error. Please try again.', true);
        }
    });

    // Function to add a message to the chat
    function addMessage(sender, text, isAI = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex items-start space-x-3';
        
        const avatar = document.createElement('div');
        avatar.className = 'flex-shrink-0';
        avatar.innerHTML = `
            <div class="w-8 h-8 rounded-full ${isAI ? 'bg-indigo-600' : 'bg-gray-600'} flex items-center justify-center text-white">
                ${isAI ? 'AI' : 'You'}
            </div>
        `;
        
        const content = document.createElement('div');
        content.className = 'flex-1 bg-gray-100 rounded-lg p-4';
        content.innerHTML = `<p class="text-gray-800 whitespace-pre-line">${text}</p>`;
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        chatMessages.appendChild(messageDiv);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Function to load chat history
    async function loadChatHistory() {
        try {
            const response = await fetch('/chat-history');
            const data = await response.json();
            
            chatHistory.innerHTML = '';
            data.chats.forEach(chat => {
                const chatItem = document.createElement('div');
                chatItem.className = `p-3 rounded-lg hover:bg-gray-100 cursor-pointer ${chat.id === currentChatId ? 'bg-gray-100' : ''}`;
                chatItem.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <div class="text-sm font-medium text-gray-900">${chat.preview}</div>
                            <div class="text-xs text-gray-500">${new Date(chat.timestamp).toLocaleString()}</div>
                        </div>
                        <button class="delete-chat ml-2 p-1 text-gray-400 hover:text-red-500 rounded-full hover:bg-gray-200" data-chat-id="${chat.id}">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                        </button>
                    </div>
                `;
                
                // Add click handler for the chat item
                chatItem.querySelector('.flex-1').addEventListener('click', () => loadChat(chat.id));
                
                // Add click handler for the delete button
                chatItem.querySelector('.delete-chat').addEventListener('click', async (e) => {
                    e.stopPropagation(); // Prevent chat loading when clicking delete
                    if (confirm('Are you sure you want to delete this chat?')) {
                        try {
                            const response = await fetch(`/chat/${chat.id}`, {
                                method: 'DELETE',
                                headers: {
                                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                                }
                            });
                            
                            if (response.ok) {
                                // If the deleted chat was the current one, clear the chat
                                if (chat.id === currentChatId) {
                                    chatMessages.innerHTML = '';
                                    currentChatId = null;
                                }
                                // Reload chat history
                                loadChatHistory();
                            } else {
                                alert('Failed to delete chat. Please try again.');
                            }
                        } catch (error) {
                            console.error('Error deleting chat:', error);
                            alert('Failed to delete chat. Please try again.');
                        }
                    }
                });
                
                chatHistory.appendChild(chatItem);
            });
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }

    // Function to load a specific chat
    async function loadChat(chatId) {
        try {
            const response = await fetch(`/chat/${chatId}`);
            const data = await response.json();
            
            // Clear current chat
            chatMessages.innerHTML = '';
            
            // Add messages from the loaded chat
            data.messages.forEach(message => {
                addMessage(message.sender, message.text, message.sender === 'AI');
            });
            
            currentChatId = chatId;
            
            // Update chat history to highlight current chat
            loadChatHistory();
        } catch (error) {
            console.error('Error loading chat:', error);
        }
    }
}); 