'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Fish, TrendingUp, Wifi, WifiOff, Settings, Search } from 'lucide-react';
import { asiOneClient, AgentDiscoveryResult } from '@/lib/asi-one';

interface Message {
  id: string;
  content: string;
  isUser: boolean;
  timestamp: Date;
  source?: 'local-mailbox' | 'asi-one';
}

interface ConnectionStatus {
  local: boolean;
  asiOne: boolean;
  activeAgent?: AgentDiscoveryResult;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      content: "👋 Welcome to Hyperliquid Whale Watcher! I can help you track large deposits and analyze whale trading activity. Try asking 'status', 'alerts', or 'help' for available commands.",
      isUser: false,
      timestamp: new Date()
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    local: false,
    asiOne: false
  });
  const [availableAgents, setAvailableAgents] = useState<AgentDiscoveryResult[]>([]);
  const [showAgentSelector, setShowAgentSelector] = useState(false);
  const [preferLocal, setPreferLocal] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Check connection status and discover agents on component mount
  useEffect(() => {
    checkConnectionStatus();
    discoverAgents();
  }, []);

  const checkConnectionStatus = async () => {
    try {
      const response = await fetch('/api/whale');
      if (response.ok) {
        const data = await response.json();
        setConnectionStatus({
          local: data.communication?.localMailbox?.configured || false,
          asiOne: data.communication?.asiOne?.configured || false
        });
      }
    } catch (error) {
      console.error('Failed to check connection status:', error);
    }
  };

  const discoverAgents = async () => {
    try {
      console.log('Starting agent discovery...');
      const agents = await asiOneClient.discoverAgents();
      console.log('Discovered agents:', agents);
      setAvailableAgents(agents);
      
      // Set the first available agent as active
      if (agents.length > 0) {
        console.log('Setting active agent:', agents[0]);
        setConnectionStatus(prev => ({
          ...prev,
          activeAgent: agents[0]
        }));
      } else {
        console.log('No agents discovered');
      }
    } catch (error) {
      console.error('Failed to discover agents:', error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: input.trim(),
      isUser: true,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      let response;
      let source: 'local-mailbox' | 'asi-one' = 'local-mailbox';

      console.log('Sending message with preferLocal:', preferLocal);
      console.log('Connection status:', connectionStatus);

      if (preferLocal && connectionStatus.local) {
        // Try local mailbox first
        console.log('Using local mailbox');
        response = await fetch('/api/mailbox', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ 
            to: 'whale-agent',
            message: input.trim(),
            type: 'query'
          }),
        });
      } else if (!preferLocal && connectionStatus.asiOne) {
        // Use ASI:One - find the ASI:One agent from available agents
        const asiOneAgent = availableAgents.find(agent => agent.source === 'asi-one');
        console.log('Using ASI:One with agent:', asiOneAgent);
        
        if (asiOneAgent) {
          const asiResponse = await asiOneClient.sendMessage(
            input.trim(),
            asiOneAgent.address
          );
          
          if (asiResponse.success) {
             response = {
               ok: true,
               json: async () => ({
                 success: true,
                 response: asiResponse.message || 'No response received',
                 source: 'asi-one'
               })
             };
             source = 'asi-one';
           } else {
             throw new Error(asiResponse.error || 'ASI:One communication failed');
           }
        } else {
          throw new Error('ASI:One agent not available');
        }
      } else {
        console.log('No communication method available - preferLocal:', preferLocal, 'connectionStatus:', connectionStatus);
        throw new Error('No communication method available');
      }

      if (response && response.ok) {
        const data = await response.json();
        
        if (data.success) {
          // Handle different response formats
          let responseText = '';
          if (data.response) {
            responseText = data.response; // Mailbox format
          } else if (data.message) {
            responseText = data.message; // ASI:One format
          } else if (data.data) {
            responseText = data.data; // Alternative format
          } else {
            responseText = JSON.stringify(data, null, 2);
          }

          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            content: responseText,
            isUser: false,
            timestamp: new Date(),
            source: data.source || source
          };
          setMessages(prev => [...prev, botMessage]);
        } else {
          throw new Error(data.error || 'Failed to get response');
        }
      } else {
        throw new Error('Failed to get response');
      }
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        isUser: false,
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatMessage = (content: string) => {
    // Convert markdown-style formatting to HTML
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code class="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded text-sm font-mono">$1</code>')
      .replace(/\n/g, '<br />');
  };

  const quickActions = [
    { label: 'Show recent whales', icon: Fish },
    { label: 'Whale activity today', icon: TrendingUp },
  ];

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto">
      {/* Header with connection status and controls */}
      <div className="flex-shrink-0 border-b border-gray-200 dark:border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center">
              <Fish className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                Hyperliquid Whale Watcher
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Real-time whale detection and trading intelligence
              </p>
            </div>
          </div>
          
          {/* Connection Status and Controls */}
          <div className="flex items-center space-x-4">
            {/* Connection Status Indicators */}
            <div className="flex items-center space-x-2">
              <div className="flex items-center space-x-1">
                {connectionStatus.local ? (
                  <Wifi className="h-4 w-4 text-green-500" />
                ) : (
                  <WifiOff className="h-4 w-4 text-gray-400" />
                )}
                <span className="text-xs text-gray-600 dark:text-gray-400">Local</span>
              </div>
              <div className="flex items-center space-x-1">
                {connectionStatus.asiOne ? (
                  <Wifi className="h-4 w-4 text-blue-500" />
                ) : (
                  <WifiOff className="h-4 w-4 text-gray-400" />
                )}
                <span className="text-xs text-gray-600 dark:text-gray-400">ASI:One</span>
              </div>
            </div>

            {/* Agent Selector */}
            {availableAgents.length > 0 && (
              <div className="relative">
                <button
                  onClick={() => setShowAgentSelector(!showAgentSelector)}
                  className="flex items-center space-x-1 px-3 py-1 bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 rounded-md hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors"
                >
                  <Search className="h-4 w-4" />
                  <span className="text-sm">
                    {connectionStatus.activeAgent?.name || 'Select Agent'}
                  </span>
                </button>
                
                {showAgentSelector && (
                  <div className="absolute right-0 mt-2 w-64 bg-white dark:bg-gray-800 rounded-md shadow-lg border dark:border-gray-600 z-10">
                    <div className="p-2">
                      <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Available Agents</div>
                      {availableAgents.map((agent, index) => (
                        <button
                          key={agent.address}
                          onClick={() => {
                            setConnectionStatus(prev => ({ ...prev, activeAgent: agent }));
                            setShowAgentSelector(false);
                          }}
                          className={`w-full text-left p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 ${
                            connectionStatus.activeAgent?.address === agent.address
                              ? 'bg-blue-50 dark:bg-blue-900 border-l-2 border-blue-500'
                              : ''
                          }`}
                        >
                          <div className="font-medium text-sm text-gray-900 dark:text-white">{agent.name}</div>
                          <div className="text-xs text-gray-500 dark:text-gray-400 truncate">{agent.description}</div>
                          <div className="flex items-center space-x-2 mt-1">
                            <span className={`inline-block w-2 h-2 rounded-full ${
                              agent.isOnline ? 'bg-green-400' : 'bg-gray-400'
                            }`}></span>
                            <span className="text-xs text-gray-400">{agent.source}</span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Communication Preference Toggle */}
            <div className="flex items-center space-x-2">
              <label className="flex items-center space-x-1 cursor-pointer">
                <input
                  type="checkbox"
                  checked={preferLocal}
                  onChange={(e) => setPreferLocal(e.target.checked)}
                  className="rounded"
                />
                <span className="text-xs text-gray-600 dark:text-gray-400">Prefer Local</span>
              </label>
            </div>

            {/* Refresh Button */}
            <button
              onClick={() => {
                checkConnectionStatus();
                discoverAgents();
              }}
              className="p-2 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
            >
              <Settings className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.isUser
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white'
              }`}
            >
              <div
                className="whitespace-pre-wrap"
                dangerouslySetInnerHTML={{ __html: formatMessage(message.content) }}
              />
              <div className="flex items-center justify-between mt-1">
                <div
                  className={`text-xs ${
                    message.isUser ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
                  }`}
                >
                  {message.timestamp.toLocaleTimeString()}
                </div>
                {!message.isUser && message.source && (
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    message.source === 'local-mailbox' 
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
                  }`}>
                    {message.source === 'local-mailbox' ? 'Local' : 'ASI:One'}
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-2 flex items-center space-x-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-gray-600 dark:text-gray-300">Analyzing whale activity...</span>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Actions */}
      {messages.length === 1 && (
        <div className="flex-shrink-0 p-4 border-t border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">Quick actions:</p>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action) => (
              <button
                key={action.label}
                onClick={() => setInput(action.label)}
                className="flex items-center space-x-2 px-3 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 rounded-lg text-sm transition-colors"
              >
                <action.icon className="w-4 h-4" />
                <span>{action.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="flex-shrink-0 border-t border-gray-200 dark:border-gray-700 p-4">
        <div className="flex space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about whale activity or provide a wallet address..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:text-white"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}