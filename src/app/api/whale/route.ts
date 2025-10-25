import { NextRequest, NextResponse } from 'next/server';
import { asiOneClient, isASIOneConfigured } from '@/lib/asi-one';

export async function POST(request: NextRequest) {
  try {
    const { message } = await request.json();

    if (!message || typeof message !== 'string') {
      return NextResponse.json(
        { error: 'Message is required and must be a string' },
        { status: 400 }
      );
    }

    let response: string;

    // Use ASI:ONE to communicate with deployed agent
    if (isASIOneConfigured()) {
      try {
        const asiResponse = await asiOneClient.sendMessage(message);
        if (asiResponse.success && asiResponse.message) {
          response = asiResponse.message;
        } else {
          throw new Error(asiResponse.error || 'ASI:ONE request failed');
        }
      } catch (error) {
        console.error('ASI:ONE request failed:', error);
        return NextResponse.json(
          { 
            error: 'Agent communication failed',
            message: 'Unable to connect to the Hyperliquid Whale Watcher agent. Please check if the agent is deployed and configured correctly.'
          },
          { status: 503 }
        );
      }
    } else {
      return NextResponse.json(
        { 
          error: 'Agent not configured',
          message: 'ASI:ONE client is not configured. Please set up the required environment variables.'
        },
        { status: 503 }
      );
    }

    return NextResponse.json({
      success: true,
      response,
      timestamp: new Date().toISOString(),
      source: 'asi-one'
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
  // Health check endpoint
  return NextResponse.json({
    status: 'healthy',
    agent: 'Hyperliquid Whale Watcher',
    asiOneConfigured: isASIOneConfigured(),
    timestamp: new Date().toISOString()
  });
}