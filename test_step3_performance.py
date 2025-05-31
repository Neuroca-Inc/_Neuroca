#!/usr/bin/env python3
"""
Test Step 3 (static analysis) performance with the new filtering.
"""

import sys
import asyncio
import time
from pathlib import Path
sys.path.insert(0, 'src')

from src.neuroca.analysis.summarization_engine import CodebaseSummarizationEngine, ScopeConfig

async def test_step3_performance():
    """Test Step 3 performance with the enhanced filtering."""
    print("🧪 Testing Step 3 (Static Analysis) Performance")
    print("=" * 50)
    
    # Create scope config
    scope = ScopeConfig(
        repos=["main"],
        branches=["main"]
    )
    
    # Create engine
    print("📦 Creating summarization engine...")
    engine = CodebaseSummarizationEngine(scope, ".")
    
    print(f"🎯 Expected files to process: ~839 (based on filtering test)")
    
    # Time Step 3 execution
    print(f"\n⏱️  Starting Step 3: Static Analysis...")
    start_time = time.time()
    
    try:
        await engine._static_analysis()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ Step 3 completed successfully!")
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"📊 Files processed: {len(engine.file_metadata)}")
        print(f"🚀 Processing rate: {len(engine.file_metadata) / duration:.1f} files/second")
        
        # Show some statistics
        languages = {}
        total_loc = 0
        for metadata in engine.file_metadata.values():
            lang = metadata.language
            languages[lang] = languages.get(lang, 0) + 1
            total_loc += metadata.lines_of_code
        
        print(f"\n📈 Analysis Results:")
        print(f"   Total Lines of Code: {total_loc:,}")
        print(f"   Languages found: {len(languages)}")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"     • {lang}: {count} files")
        
        return True
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"❌ Step 3 failed after {duration:.2f} seconds")
        print(f"🚨 Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_step3_performance())
