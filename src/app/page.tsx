export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Hyperliquid Whale Watcher
          </h1>
          <p className="text-lg text-gray-600">
            Real-time whale deposit tracking and trading intelligence
          </p>
        </div>
        
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="mb-4">
            <h2 className="text-xl font-semibold text-gray-800 mb-2">
              Ask about whale activity
            </h2>
            <p className="text-gray-600 text-sm">
              Try asking: "Which whales just made big moves?" or "Show me recent large deposits"
            </p>
          </div>
          
          <div className="space-y-4">
            <div className="border rounded-lg p-4 min-h-[300px] bg-gray-50">
              <p className="text-gray-500 text-center mt-20">
                Chat interface will be implemented here
              </p>
            </div>
            
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ask about whale activity..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                Send
              </button>
            </div>
          </div>
        </div>
        
        <div className="mt-8 text-center text-sm text-gray-500">
          <p>Research use only, not financial advice.</p>
        </div>
      </div>
    </main>
  )
}