import { NextRequest, NextResponse } from 'next/server';
import { asiOneClient, isASIOneConfigured, isLocalMailboxConfigured } from '@/lib/asi-one';

export async function POST(request: NextRequest) {
  try {
    const { message, preferLocal = true } = await request.json();

    if (!message || typeof message !== 'string') {
      return NextResponse.json(
        { error: 'Message is required and must be a string' },
        { status: 400 }
      );
    }

    let response: string;
    let source: string;

    // Try local mailbox first if preferred and configured
    if (preferLocal && isLocalMailboxConfigured()) {
      try {
        const localResponse = await fetch(`${process.env.NEXT_PUBLIC_LOCAL_MAILBOX_URL || 'http://localhost:8000'}/send`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            to: process.env.NEXT_PUBLIC_WHALE_AGENT_ADDRESS || 'agent1qfe8jqus8ka24sneygllla33uv5qxcc63rq6pxqmpmhk3mcga72mungnmne',
            message,
            type: 'query'
          })
        });

        if (localResponse.ok) {
          const data = await localResponse.json();
          if (data.success && data.response) {
            response = data.response;
            source = 'local-mailbox';
          } else {
            throw new Error('Local mailbox returned no response');
          }
        } else {
          throw new Error(`Local mailbox error: ${localResponse.status}`);
        }
      } catch (error) {
        console.warn('Local mailbox failed, trying ASI:ONE:', error);
        
        // Fallback to ASI:ONE
        if (isASIOneConfigured()) {
          try {
            const asiResponse = await asiOneClient.sendMessage(message);
            if (asiResponse.success && asiResponse.message) {
              response = asiResponse.message;
              source = 'asi-one';
            } else {
              throw new Error(asiResponse.error || 'ASI:ONE request failed');
            }
          } catch (asiError) {
            console.error('Both local and ASI:ONE failed:', asiError);
            return NextResponse.json(
              { 
                error: 'All agent communication methods failed',
                message: 'Unable to connect to any whale agent. Please check if agents are running and configured correctly.'
              },
              { status: 503 }
            );
          }
        } else {
          return NextResponse.json(
            { 
              error: 'No agent communication available',
              message: 'Neither local mailbox nor ASI:ONE is properly configured.'
            },
            { status: 503 }
          );
        }
      }
    } else if (isASIOneConfigured()) {
      // Use ASI:ONE directly
      try {
        const asiResponse = await asiOneClient.sendMessage(message);
        if (asiResponse.success && asiResponse.message) {
          response = asiResponse.message;
          source = 'asi-one';
        } else {
          throw new Error(asiResponse.error || 'ASI:ONE request failed');
        }
      } catch (error) {
        console.error('ASI:ONE request failed:', error);
        return NextResponse.json(
          { 
            error: 'Agent communication failed',
            message: 'Unable to connect to the Hyperliquid Whale Watcher agent via ASI:ONE. Please check if the agent is deployed and configured correctly.'
          },
          { status: 503 }
        );
      }
    } else {
      return NextResponse.json(
        { 
          error: 'No agent configured',
          message: 'Neither local mailbox nor ASI:ONE client is configured. Please set up the required environment variables.'
        },
        { status: 503 }
      );
    }

    return NextResponse.json({
      success: true,
      response,
      timestamp: new Date().toISOString(),
      source
    });

  } catch (error) {
    console.error('API Error:', error);
    
    return NextResponse.json(
      { 
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  // Health check endpoint with enhanced status
  const localConfigured = isLocalMailboxConfigured();
  const asiConfigured = isASIOneConfigured();
  
  return NextResponse.json({
    status: 'healthy',
    agent: 'Hyperliquid Whale Watcher',
    communication: {
      localMailbox: {
        configured: localConfigured,
        url: process.env.NEXT_PUBLIC_LOCAL_MAILBOX_URL || 'http://localhost:8000'
      },
      asiOne: {
        configured: asiConfigured,
        url: process.env.NEXT_PUBLIC_ASI_ONE_URL || 'https://api.asi.one'
      }
    },
    agentAddress: process.env.NEXT_PUBLIC_WHALE_AGENT_ADDRESS || 'agent1qfe8jqus8ka24sneygllla33uv5qxcc63rq6pxqmpmhk3mcga72mungnmne',
    timestamp: new Date().toISOString()
  });
}