"""
Load testing script for Reward Decision Service.

This script performs load testing with proper error handling, statistics,
and response validation.
"""

import httpx
import random
import time
import threading
import uuid
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict
import statistics


class LoadTestStats:
    """Statistics collector for load testing."""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.latencies: List[float] = []
        self.success_count = 0
        self.error_count = 0
        self.status_codes: Dict[int, int] = defaultdict(int)
        self.errors: Dict[str, int] = defaultdict(int)
        self.timeouts = 0
        self.response_times: List[float] = []
        
    def record_success(self, latency: float, status_code: int, response_time: float):
        """Record a successful request."""
        with self.lock:
            self.latencies.append(latency)
            self.success_count += 1
            self.status_codes[status_code] += 1
            self.response_times.append(response_time)
    
    def record_error(self, error_type: str, latency: Optional[float] = None):
        """Record a failed request."""
        with self.lock:
            self.error_count += 1
            self.errors[error_type] += 1
            if latency is not None:
                self.latencies.append(latency)
            if error_type == "Timeout":
                self.timeouts += 1
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics."""
        with self.lock:
            total = self.success_count + self.error_count
            if total == 0:
                return {"error": "No requests completed"}
            
            stats = {
                "total_requests": total,
                "successful": self.success_count,
                "failed": self.error_count,
                "success_rate": f"{(self.success_count / total * 100):.2f}%",
                "error_rate": f"{(self.error_count / total * 100):.2f}%",
                "timeouts": self.timeouts,
                "status_codes": dict(self.status_codes),
                "errors": dict(self.errors)
            }
            
            if self.latencies:
                sorted_latencies = sorted(self.latencies)
                n = len(sorted_latencies)
                stats["latency_ms"] = {
                    "min": round(min(sorted_latencies), 2),
                    "max": round(max(sorted_latencies), 2),
                    "mean": round(statistics.mean(sorted_latencies), 2),
                    "median": round(statistics.median(sorted_latencies), 2),
                    "p50": round(sorted_latencies[int(0.5 * n)], 2) if n > 0 else 0,
                    "p95": round(sorted_latencies[int(0.95 * n)], 2) if n > 0 else 0,
                    "p99": round(sorted_latencies[int(0.99 * n)], 2) if n > 0 else 0,
                    "p999": round(sorted_latencies[int(0.999 * n)], 2) if n > 0 and n > 1 else 0,
                }
                
                if len(sorted_latencies) > 1:
                    stats["latency_ms"]["stdev"] = round(statistics.stdev(sorted_latencies), 2)
            
            if self.response_times:
                stats["response_times_ms"] = {
                    "mean": round(statistics.mean(self.response_times), 2),
                    "median": round(statistics.median(self.response_times), 2),
                }
            
            return stats


def validate_response(response: httpx.Response) -> bool:
    """Validate that the response has the expected structure."""
    try:
        if response.status_code != 200:
            return False
        
        data = response.json()
        required_fields = ["decision_id", "policy_version", "reward_type", 
                          "reward_value", "xp", "reason_codes", "meta"]
        
        for field in required_fields:
            if field not in data:
                return False
        
        # Validate reward_type is valid
        valid_reward_types = ["XP", "CHECKOUT", "GOLD"]
        if data.get("reward_type") not in valid_reward_types:
            return False
        
        return True
    except Exception:
        return False


def send_request(
    client: httpx.Client,
    url: str,
    stats: LoadTestStats,
    timeout: float = 5.0,
    warmup: bool = False
):
    """Send a single request and record statistics."""
    payload = {
        "txn_id": f"txn_{uuid.uuid4()}",
        "user_id": f"user_{random.randint(1, 100)}",
        "merchant_id": f"merchant_{random.randint(1, 5)}",
        "amount": round(random.uniform(10.0, 500.0), 2),  # Use float for amount
        "txn_type": "PAYMENT",  # Use TransactionType.PAYMENT enum value in production
        "ts": datetime.now().isoformat()
    }
    
    start_time = time.time()
    error_type = None
    
    try:
        response = client.post(url, json=payload, timeout=timeout)
        latency = (time.time() - start_time) * 1000
        
        # Calculate response time (time to first byte)
        response_time = latency
        
        if response.status_code == 200:
            if validate_response(response):
                stats.record_success(latency, response.status_code, response_time)
            else:
                stats.record_error("InvalidResponse", latency)
        else:
            stats.record_error(f"HTTP_{response.status_code}", latency)
            stats.record_success(latency, response.status_code, response_time)  # Still record latency
            
    except httpx.TimeoutException:
        latency = (time.time() - start_time) * 1000
        stats.record_error("Timeout", latency)
    except httpx.ConnectError:
        latency = (time.time() - start_time) * 1000
        stats.record_error("ConnectionError", latency)
    except httpx.HTTPStatusError as e:
        latency = (time.time() - start_time) * 1000
        stats.record_error(f"HTTPError_{e.response.status_code}", latency)
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        error_type = type(e).__name__
        stats.record_error(error_type, latency)


def worker(
    client: httpx.Client,
    url: str,
    stats: LoadTestStats,
    num_requests: int,
    timeout: float,
    warmup: bool = False
):
    """Worker thread that sends multiple requests."""
    for _ in range(num_requests):
        send_request(client, url, stats, timeout, warmup)


def run_load_test(
    url: str = "http://127.0.0.1:8000/reward/decide",
    total_requests: int = 300,
    concurrency: int = 50,
    timeout: float = 5.0,
    warmup_requests: int = 10
):
    """Run the load test with proper concurrency control."""
    print(f"\n{'='*60}")
    print(f"Load Test Configuration")
    print(f"{'='*60}")
    print(f"URL: {url}")
    print(f"Total Requests: {total_requests}")
    print(f"Concurrency: {concurrency}")
    print(f"Timeout: {timeout}s")
    print(f"Warmup Requests: {warmup_requests}")
    print(f"{'='*60}\n")
    
    stats = LoadTestStats()
    
    # Warm-up phase
    if warmup_requests > 0:
        print("Warming up service...")
        warmup_stats = LoadTestStats()
        with httpx.Client() as client:
            for _ in range(warmup_requests):
                send_request(client, url, warmup_stats, timeout, warmup=True)
        print(f"Warmup complete: {warmup_stats.success_count}/{warmup_requests} successful\n")
    
    # Main load test
    print("Starting load test...")
    start_time = time.time()
    
    requests_per_thread = total_requests // concurrency
    remaining_requests = total_requests % concurrency
    
    threads = []
    
    # Create threads with proper concurrency control
    for i in range(concurrency):
        num_reqs = requests_per_thread + (1 if i < remaining_requests else 0)
        if num_reqs == 0:
            continue
            
        # Each thread gets its own client for connection pooling
        client = httpx.Client(timeout=timeout)
        t = threading.Thread(
            target=worker,
            args=(client, url, stats, num_reqs, timeout),
            daemon=True
        )
        t.start()
        threads.append((t, client))
    
    # Wait for all threads to complete
    for t, client in threads:
        t.join()
        client.close()  # Close client after thread completes
    
    total_time = time.time() - start_time
    
    # Print results
    print(f"\n{'='*60}")
    print(f"Load Test Results")
    print(f"{'='*60}")
    
    results = stats.get_stats()
    
    if "error" in results:
        print(f"Error: {results['error']}")
        return
    
    print(f"\nRequest Summary:")
    print(f"  Total Requests: {results['total_requests']}")
    print(f"  Successful: {results['successful']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Success Rate: {results['success_rate']}")
    print(f"  Error Rate: {results['error_rate']}")
    print(f"  Timeouts: {results['timeouts']}")
    
    if results.get('status_codes'):
        print(f"\nStatus Codes:")
        for code, count in sorted(results['status_codes'].items()):
            print(f"  {code}: {count}")
    
    if results.get('errors'):
        print(f"\nErrors:")
        for error_type, count in sorted(results['errors'].items()):
            print(f"  {error_type}: {count}")
    
    if results.get('latency_ms'):
        print(f"\nLatency Statistics (ms):")
        latency = results['latency_ms']
        print(f"  Min: {latency['min']}")
        print(f"  Max: {latency['max']}")
        print(f"  Mean: {latency['mean']}")
        print(f"  Median: {latency['median']}")
        if 'stdev' in latency:
            print(f"  Std Dev: {latency['stdev']}")
        print(f"  P50: {latency['p50']}")
        print(f"  P95: {latency['p95']}")
        print(f"  P99: {latency['p99']}")
        if latency.get('p999'):
            print(f"  P99.9: {latency['p999']}")
    
    print(f"\nTest Duration: {total_time:.2f}s")
    if results['total_requests'] > 0:
        rps = results['total_requests'] / total_time
        print(f"Requests per Second: {rps:.2f}")
    
    print(f"{'='*60}\n")


def main():
    """Main entry point with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Load test script for Reward Decision Service",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://127.0.0.1:8000/reward/decide",
        help="Service URL (default: http://127.0.0.1:8000/reward/decide)"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=300,
        help="Total number of requests (default: 300)"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Number of concurrent threads (default: 50)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Request timeout in seconds (default: 5.0)"
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=10,
        help="Number of warmup requests (default: 10)"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.requests <= 0:
        print("Error: --requests must be greater than 0")
        return
    
    if args.concurrency <= 0:
        print("Error: --concurrency must be greater than 0")
        return
    
    if args.timeout <= 0:
        print("Error: --timeout must be greater than 0")
        return
    
    run_load_test(
        url=args.url,
        total_requests=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
        warmup_requests=args.warmup
    )


if __name__ == "__main__":
    main()
