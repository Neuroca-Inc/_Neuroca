"""
Comprehensive benchmark suite for comparing memory systems.
"""
import time
import statistics
import random
import string
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from .base import MemorySystemInterface, MemoryEntry
from .competitors.simple_dict import SimpleDictMemory
from .competitors.sqlite_memory import SQLiteMemory
from .competitors.langchain_inspired import LangChainInspiredMemory
from .competitors.vector_memory import SimpleVectorMemory
from .competitors.neuroca_memory import NeurocognitiveArchitectureMemory


@dataclass
class BenchmarkResult:
    """Results from a single benchmark operation."""
    operation: str
    system_name: str
    data_size: int
    execution_time: float
    success: bool
    memory_usage_mb: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class SystemBenchmarkSuite:
    """Complete benchmark results for a memory system."""
    system_name: str
    system_metadata: Dict[str, Any]
    results: List[BenchmarkResult]
    total_time: float
    
    def get_operation_stats(self, operation: str) -> Dict[str, float]:
        """Get statistics for a specific operation."""
        op_results = [r.execution_time for r in self.results if r.operation == operation and r.success]
        
        if not op_results:
            return {"count": 0, "mean": 0.0, "median": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        
        return {
            "count": len(op_results),
            "mean": statistics.mean(op_results),
            "median": statistics.median(op_results),
            "std": statistics.stdev(op_results) if len(op_results) > 1 else 0.0,
            "min": min(op_results),
            "max": max(op_results)
        }


class MemorySystemBenchmark:
    """Benchmark runner for memory systems comparison."""
    
    def __init__(self, output_dir: str = "benchmarks/memory_systems_comparison/results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test data generation settings
        self.random_seed = 42
        random.seed(self.random_seed)
    
    def generate_test_data(self, count: int, avg_content_length: int = 100) -> List[MemoryEntry]:
        """Generate realistic test data for benchmarking."""
        entries = []
        topics = ["AI", "ML", "NLP", "data science", "technology", "research", "development", "software"]
        roles = ["user", "assistant", "system"]
        
        for i in range(count):
            # Generate content
            topic = random.choice(topics)
            content_length = max(10, int(random.gauss(avg_content_length, avg_content_length // 4)))
            
            content = f"This is a memory entry about {topic}. " + "".join(
                random.choices(string.ascii_letters + string.digits + " .,!?", k=content_length)
            )
            
            # Generate metadata
            metadata = {
                "topic": topic,
                "role": random.choice(roles),
                "importance": random.random(),
                "session_id": f"session_{random.randint(1, 10)}",
                "entry_type": random.choice(["conversation", "fact", "instruction", "observation"]),
                "tags": random.sample(["important", "technical", "casual", "urgent", "reference"], 
                                     random.randint(1, 3))
            }
            
            entry = MemoryEntry(
                id=f"entry_{i:06d}",
                content=content,
                metadata=metadata,
                timestamp=time.time() - random.uniform(0, 86400)  # Random time in last 24h
            )
            entries.append(entry)
        
        return entries
    
    def benchmark_operation(self, system: MemorySystemInterface, operation_name: str, 
                          operation_func: Callable, data_size: int, 
                          iterations: int = 1) -> List[BenchmarkResult]:
        """Benchmark a specific operation on a memory system."""
        results = []
        
        for i in range(iterations):
            try:
                start_time = time.time()
                success = operation_func()
                end_time = time.time()
                
                execution_time = end_time - start_time
                
                result = BenchmarkResult(
                    operation=operation_name,
                    system_name=system.get_name(),
                    data_size=data_size,
                    execution_time=execution_time,
                    success=bool(success),
                    metadata={"iteration": i + 1}
                )
                results.append(result)
                
            except Exception as e:
                result = BenchmarkResult(
                    operation=operation_name,
                    system_name=system.get_name(),
                    data_size=data_size,
                    execution_time=0.0,
                    success=False,
                    metadata={"error": str(e), "iteration": i + 1}
                )
                results.append(result)
        
        return results
    
    def benchmark_system(self, system: MemorySystemInterface, 
                        data_sizes: List[int] = [100, 500, 1000],
                        iterations: int = 3) -> SystemBenchmarkSuite:
        """Run comprehensive benchmarks on a memory system."""
        print(f"Benchmarking {system.get_name()}...")
        total_start_time = time.time()
        all_results = []
        
        for data_size in data_sizes:
            print(f"  Testing with {data_size} entries...")
            
            # Generate test data
            test_entries = self.generate_test_data(data_size)
            search_queries = [
                "AI technology",
                "machine learning",
                "data science research",
                "software development",
                "important technical"
            ]
            
            # Clear system before each test
            system.clear()
            
            # 1. Store operations
            def store_all():
                for entry in test_entries:
                    system.store(entry)
                return True
            
            store_results = self.benchmark_operation(
                system, "store_batch", store_all, data_size, iterations
            )
            all_results.extend(store_results)
            
            # 2. Individual store operations
            system.clear()
            def store_single():
                entry = random.choice(test_entries)
                return system.store(entry)
            
            single_store_results = self.benchmark_operation(
                system, "store_single", store_single, data_size, iterations * 10
            )
            all_results.extend(single_store_results)
            
            # Setup for other operations
            for entry in test_entries:
                system.store(entry)
            
            # 3. Retrieve operations
            def retrieve_random():
                entry_id = random.choice(test_entries).id
                return system.retrieve(entry_id) is not None
            
            retrieve_results = self.benchmark_operation(
                system, "retrieve", retrieve_random, data_size, iterations * 10
            )
            all_results.extend(retrieve_results)
            
            # 4. Search operations
            def search_random():
                query = random.choice(search_queries)
                results = system.search(query, limit=10)
                return len(results)
            
            search_results = self.benchmark_operation(
                system, "search", search_random, data_size, iterations * 5
            )
            all_results.extend(search_results)
            
            # 5. Update operations
            def update_random():
                entry = random.choice(test_entries)
                entry.content = "Updated: " + entry.content
                return system.update(entry.id, entry)
            
            update_results = self.benchmark_operation(
                system, "update", update_random, data_size, iterations * 5
            )
            all_results.extend(update_results)
            
            # 6. Delete operations
            def delete_random():
                entry_id = random.choice(test_entries).id
                return system.delete(entry_id)
            
            delete_results = self.benchmark_operation(
                system, "delete", delete_random, data_size, iterations * 5
            )
            all_results.extend(delete_results)
            
            # 7. List operations
            def list_entries():
                entries = system.list_all(limit=100)
                return len(entries)
            
            list_results = self.benchmark_operation(
                system, "list", list_entries, data_size, iterations
            )
            all_results.extend(list_results)
        
        total_time = time.time() - total_start_time
        print(f"  Completed in {total_time:.2f}s")
        
        return SystemBenchmarkSuite(
            system_name=system.get_name(),
            system_metadata=system.get_metadata(),
            results=all_results,
            total_time=total_time
        )
    
    def run_comparison_benchmark(self, data_sizes: List[int] = [100, 500, 1000],
                                iterations: int = 3) -> Dict[str, SystemBenchmarkSuite]:
        """Run benchmarks on all memory systems."""
        print("Starting Memory Systems Comparison Benchmark")
        print("=" * 60)
        
        # Initialize all systems
        systems = [
            SimpleDictMemory(),
            SQLiteMemory(),
            LangChainInspiredMemory(),
            SimpleVectorMemory(),
            NeurocognitiveArchitectureMemory()
        ]
        
        results = {}
        
        for system in systems:
            try:
                suite_result = self.benchmark_system(system, data_sizes, iterations)
                results[system.get_name()] = suite_result
            except Exception as e:
                print(f"Error benchmarking {system.get_name()}: {e}")
                continue
        
        # Save results
        self.save_results(results)
        
        return results
    
    def save_results(self, results: Dict[str, SystemBenchmarkSuite]) -> str:
        """Save benchmark results to JSON file."""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"memory_systems_benchmark_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # Convert to serializable format
        serializable_results = {}
        for system_name, suite in results.items():
            serializable_results[system_name] = {
                "system_name": suite.system_name,
                "system_metadata": suite.system_metadata,
                "total_time": suite.total_time,
                "results": [asdict(result) for result in suite.results]
            }
        
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        print(f"Results saved to: {filepath}")
        return str(filepath)


def run_benchmark():
    """Main function to run the benchmark."""
    benchmark = MemorySystemBenchmark()
    results = benchmark.run_comparison_benchmark(
        data_sizes=[50, 100, 500],  # Smaller sizes for faster testing
        iterations=3
    )
    
    print("\\nBenchmark completed!")
    for system_name, suite in results.items():
        print(f"{system_name}: {suite.total_time:.2f}s total")
    
    return results


if __name__ == "__main__":
    run_benchmark()