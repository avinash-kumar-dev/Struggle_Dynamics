"""
LLM interaction layer using Google Gemini with high thinking, grounding, and URL context
"""
import os
import json
import asyncio
from typing import Any, Optional, Type
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
LLM_MODEL = "gemini-3-flash-preview"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")


def get_ai_response(
    prompt: str,
    output_format: Type[BaseModel],
    grounding: bool = True,
    thinking_level: str = "high",
    url_context: list = None,
    model: str = None
) -> Optional[BaseModel]:
    """
    Synchronous LLM call with high thinking and grounding
    
    Args:
        prompt: The system/user prompt (can include URLs directly)
        output_format: Pydantic model class for structured output
        grounding: Enable Google Search grounding for factual accuracy
        thinking_level: Thinking level (high, medium, low, minimal)
        url_context: List of URLs for the model to retrieve content from (uses URL context tool)
        
    Returns:
        Parsed Pydantic model instance or None on error
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        active_model = model or LLM_MODEL

        # Build tools list
        tools = []
        
        # Add Google Search grounding
        if grounding:
            tools.append(types.Tool(google_search=types.GoogleSearch()))
        
        # Always add URL context tool
        tools.append(types.Tool(url_context={}))
        
        # Log URL context if provided
        if url_context and len(url_context) > 0:
            print(f"📎 URL Context: {len(url_context)} URLs provided")
            for url in url_context:
                print(f"   - {url}")
        
        # Map thinking_level string to ThinkingLevel enum
        thinking_level_map = {
            "high": types.ThinkingLevel.HIGH,
            "medium": types.ThinkingLevel.MEDIUM,
            "low": types.ThinkingLevel.LOW,
            "minimal": types.ThinkingLevel.MINIMAL,
        }
        thinking_level_enum = thinking_level_map.get(thinking_level.lower(), types.ThinkingLevel.HIGH)
        
        # Build generation config
        config_params = {
            "response_mime_type": "application/json",
            "response_json_schema": output_format.model_json_schema(),
        }
        
        # Add thinking config using thinkingLevel (new SDK parameter)
        config_params["thinking_config"] = types.ThinkingConfig(thinkingLevel=thinking_level_enum)
        
        # Add tools if any
        if tools:
            config_params["tools"] = tools
        
        url_count = len(url_context) if url_context else 0
        print(f"🔧 LLM Config: model='{active_model}', thinking_level={thinking_level}, grounding={grounding}, urls={url_count}")
        
        # Include URLs directly in prompt if provided (tool will fetch content)
        final_prompt = prompt
        if url_context and len(url_context) > 0:
            url_section = "\n\n# REFERENCE URLs (Model will retrieve content from these)\n\n"
            for i, url in enumerate(url_context, 1):
                url_section += f"{i}. {url}\n"
            url_section += "\n**Use these URLs as primary sources for market data, pricing, and competitive intelligence.**\n\n"
            final_prompt = url_section + prompt
        
        # Make request
        import time
        start_time = time.time()
        
        response = client.models.generate_content(
            model=active_model,
            contents=final_prompt,
            config=types.GenerateContentConfig(**config_params)
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Extract comprehensive token usage from response
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0
        thinking_tokens = 0
        cached_tokens = 0
        
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count_total', getattr(usage, 'prompt_token_count', 0))
            output_tokens = getattr(usage, 'candidates_token_count', 0)
            total_tokens = getattr(usage, 'total_token_count', 0)
            thinking_tokens = getattr(usage, 'thoughts_token_count', 0)
            cached_tokens = getattr(usage, 'cached_content_token_count', 0)

        
        # Extract grounding sources from metadata
        grounding_sources = []
        grounding_used = False
        search_queries = []
        grounding_chunks_data = []
        
        try:
            if response.candidates and response.candidates[0].grounding_metadata:
                metadata = response.candidates[0].grounding_metadata
                grounding_used = True  # Grounding was triggered
                
                # Extract search queries
                if hasattr(metadata, 'web_search_queries') and metadata.web_search_queries:
                    search_queries = list(metadata.web_search_queries)
                
                # Extract grounding chunks and URLs
                if metadata.grounding_chunks:
                    for chunk in metadata.grounding_chunks:
                        chunk_info = {}
                        if chunk.web and chunk.web.uri:
                            uri = chunk.web.uri
                            grounding_sources.append(uri)
                            
                            # Clean up redirect URLs - extract actual domain
                            if 'grounding-api-redirect' in uri:
                                # Extract title as the actual source since redirect URLs are opaque
                                if hasattr(chunk.web, 'title') and chunk.web.title:
                                    chunk_info['source'] = chunk.web.title
                                    chunk_info['redirect_uri'] = uri
                                else:
                                    chunk_info['source'] = 'Unknown source'
                                    chunk_info['redirect_uri'] = uri
                            else:
                                chunk_info['uri'] = uri
                                if hasattr(chunk.web, 'title') and chunk.web.title:
                                    chunk_info['title'] = chunk.web.title
                        
                        # Try to extract retrieved context/snippet at different possible locations
                        context_text = None
                        if hasattr(chunk, 'retrieved_context'):
                            context_text = chunk.retrieved_context
                        elif hasattr(chunk, 'text'):
                            context_text = chunk.text  
                        elif hasattr(chunk, 'content'):
                            context_text = chunk.content
                        elif hasattr(chunk.web, 'snippet'):
                            context_text = chunk.web.snippet
                        
                        if context_text:
                            chunk_info['snippet'] = context_text
                        
                        grounding_chunks_data.append(chunk_info)
        except Exception as e:
            print(f"⚠️  Warning: Could not extract grounding sources: {e}")
        
        # Deduplicate sources
        grounding_sources = list(set(grounding_sources))
        
        # Parse response
        if response and response.text:
            # Parse as Pydantic model using model_validate_json
            parsed = output_format.model_validate_json(response.text)
            
            print(f"✅ LLM Response parsed successfully")
            # Ensure all values are not None for formatting
            duration = duration or 0
            total_tokens = total_tokens or 0
            input_tokens = input_tokens or 0
            output_tokens = output_tokens or 0
            thinking_tokens = thinking_tokens or 0
            cached_tokens = cached_tokens or 0
            
            print(f"   ⏱️  Duration: {duration:.2f}s | 🔢 Tokens: {total_tokens:,} (in: {input_tokens:,}, out: {output_tokens:,}, thought: {thinking_tokens:,})")
            if cached_tokens > 0:
                print(f"   💾 Cached Tokens: {cached_tokens:,}")
            if grounding_used:
                print(f"   🔍 Grounding Used: YES ({len(grounding_sources)} URLs found)")
            if search_queries:
                print(f"   🔎 Search Queries: {len(search_queries)} queries")
            if grounding_sources:
                print(f"   🔗 Grounding Sources: {len(grounding_sources)} URLs")
            
            # Return tuple: (parsed_result, metrics_dict)
            metrics = {
                "duration_seconds": duration,
                "input_tokens": input_tokens or 0,
                "output_tokens": output_tokens or 0,
                "thinking_tokens": thinking_tokens or 0,
                "total_tokens": total_tokens or 0,
                "cached_tokens": cached_tokens or 0,
                "grounding_used": grounding_used,
                "grounding_sources": grounding_sources,
                "search_queries": search_queries,
                "grounding_chunks": grounding_chunks_data
            }
            return (parsed, metrics)
        else:
            print(f"❌ Empty response from LLM")
            return (None, None)
            
    except Exception as e:
        print(f"❌ LLM Error: {e}")
        return (None, None)


async def get_ai_response_async(
    prompt: str,
    output_format: Type[BaseModel],
    grounding: bool = True,
    thinking_level: str = "high",
    url_context: list = None,
    model: str = None
) -> Optional[BaseModel]:
    """
    Async LLM call - runs sync call in thread pool
    
    Args:
        prompt: The system/user prompt
        output_format: Pydantic model class for structured output
        grounding: Enable web grounding
        thinking_level: Thinking level
        url_context: List of URLs to ground analysis on
        
    Returns:
        Parsed Pydantic model instance or None
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: get_ai_response(prompt, output_format, grounding, thinking_level, url_context, model)
    )


async def batch_ai_responses(
    prompts: list[str],
    output_format: Type[BaseModel],
    grounding: bool = True,
    thinking_level: str = "high",
    url_context: list = None,
    batch_size: int = 4
) -> tuple[list[Optional[BaseModel]], dict]:
    """
    Execute multiple LLM calls in parallel batches and track metrics
    
    Args:
        prompts: List of prompts to execute
        output_format: Pydantic model class
        grounding: Enable grounding
        thinking_level: Thinking level
        url_context: List of URLs to ground analysis on
        batch_size: Number of parallel calls per batch (default: 4)
        
    Returns:
        Tuple of (list of parsed responses, aggregated metrics dict)
    """
    import time
    overall_start = time.time()
    
    print(f"\n🚀 Processing {len(prompts)} LLM calls in batches of {batch_size}...")
    
    all_results = []
    all_metrics = []
    
    # Process prompts in batches
    for i in range(0, len(prompts), batch_size):
        batch_prompts = prompts[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(prompts) + batch_size - 1) // batch_size
        
        print(f"   Batch {batch_num}/{total_batches}: Processing {len(batch_prompts)} prompts...")
        
        tasks = [
            get_ai_response_async(p, output_format, grounding, thinking_level, url_context)
            for p in batch_prompts
        ]
        
        batch_results = await asyncio.gather(*tasks)
        
        # Separate results and metrics
        for result_tuple in batch_results:
            if result_tuple and len(result_tuple) == 2:
                parsed_result, metrics = result_tuple
                all_results.append(parsed_result)
                if metrics:
                    all_metrics.append(metrics)
            else:
                all_results.append(None)
        
        print(f"   ✅ Batch {batch_num}/{total_batches} complete")
    
    overall_end = time.time()
    total_duration = overall_end - overall_start
    
    # Aggregate metrics
    total_tokens = sum(m.get("total_tokens", 0) for m in all_metrics)
    total_input_tokens = sum(m.get("input_tokens", 0) for m in all_metrics)
    total_output_tokens = sum(m.get("output_tokens", 0) for m in all_metrics)
    total_thinking_tokens = sum(m.get("thinking_tokens", 0) for m in all_metrics)
    total_cached_tokens = sum(m.get("cached_tokens", 0) for m in all_metrics)
    
    # Aggregate grounding statistics
    grounding_call_count = sum(1 for m in all_metrics if m.get("grounding_used", False))
    all_grounding_sources = []
    all_search_queries = []
    all_grounding_chunks = []
    
    for m in all_metrics:
        sources = m.get("grounding_sources", [])
        all_grounding_sources.extend(sources)
        
        queries = m.get("search_queries", [])
        all_search_queries.extend(queries)
        
        chunks = m.get("grounding_chunks", [])
        all_grounding_chunks.extend(chunks)
    
    # Deduplicate sources and queries
    all_grounding_sources = list(set(all_grounding_sources))
    all_search_queries = list(set(all_search_queries))
    
    aggregated_metrics = {
        "total_calls": len(prompts),
        "successful_calls": len(all_metrics),
        "failed_calls": len(prompts) - len(all_metrics),
        "total_duration_seconds": total_duration,
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_thinking_tokens": total_thinking_tokens,
        "total_cached_tokens": total_cached_tokens,
        "grounding_calls_count": grounding_call_count,
        "grounding_calls_percentage": f"{(grounding_call_count / len(all_metrics) * 100):.1f}%" if all_metrics else "0%",
        "grounding_sources": all_grounding_sources,
        "search_queries": all_search_queries,
        "grounding_chunks": all_grounding_chunks,
        "individual_metrics": all_metrics
    }
    
    print(f"\n✅ Completed all {len(all_results)} parallel LLM calls")
    # Ensure all values are not None for formatting
    total_tokens = total_tokens or 0
    total_input_tokens = total_input_tokens or 0
    total_output_tokens = total_output_tokens or 0
    total_thinking_tokens = total_thinking_tokens or 0
    total_cached_tokens = total_cached_tokens or 0
    total_duration = total_duration or 0
    
    print(f"   📊 Total Tokens: {total_tokens:,} (in: {total_input_tokens:,}, out: {total_output_tokens:,}, thought: {total_thinking_tokens:,})")
    if total_cached_tokens > 0:
        print(f"   💾 Cached Tokens: {total_cached_tokens:,}")
    print(f"   ⏱️  Total Duration: {total_duration:.2f}s")
    print(f"   🔍 Grounding Used: {grounding_call_count}/{len(all_metrics)} calls ({aggregated_metrics['grounding_calls_percentage']})")
    if all_search_queries:
        print(f"   🔎 Search Queries: {len(all_search_queries)} unique queries")
    if all_grounding_sources:
        print(f"   🔗 Total Grounding Sources: {len(all_grounding_sources)} unique URLs")
    
    return (all_results, aggregated_metrics)
