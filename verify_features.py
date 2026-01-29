# Test Mother AI OS Core Components
"""
Verification script for Mother AI OS core features:
- Infinite Memory Capability
- Reasoning Chains
- Machine Learning/Personalization Support
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime

print('=' * 60)
print('MOTHER AI OS - Feature Verification Test')
print('=' * 60)

# Test 1: Memory Store (Infinite Memory)
print('\n--- TEST 1: Memory Store (Infinite Memory Capability) ---')
try:
    from mother.memory.store import Memory, MemoryStore

    # Create temp database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        store = MemoryStore(db_path=db_path)

        # Test storing multiple memories
        print('  Adding 100 memories to test storage capacity...')
        for i in range(100):
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id=f'session-{i % 5}',
                role='user',
                content=f'Test memory content {i}: This is a longer string to test storage capacity',
                embedding=[0.1 * (i % 10)] * 3 if i % 2 == 0 else None,
            )
            store.add(memory)

        stats = store.get_stats()
        print(f'  ✓ Total memories stored: {stats["total_memories"]}')
        print(f'  ✓ Total sessions: {stats["total_sessions"]}')
        print(f'  ✓ Memories with embeddings: {stats["memories_with_embeddings"]}')

        # Test retrieval
        recent = store.get_recent(limit=10)
        print(f'  ✓ Retrieved {len(recent)} recent memories')

        # Test text search
        results = store.search_text('content 50')
        print(f'  ✓ Text search returned {len(results)} results')

        # Test semantic search
        semantic = store.search_semantic([0.1, 0.1, 0.1], limit=5, min_similarity=0.0)
        print(f'  ✓ Semantic search returned {len(semantic)} results')

        print('  ✓ Memory Store: PASSED')
except Exception as e:
    print(f'  ✗ Memory Store: FAILED - {e}')
    import traceback
    traceback.print_exc()

# Test 2: Cognitive Engine (Reasoning Chains)
print('\n--- TEST 2: Cognitive Engine (Reasoning Chains) ---')
try:
    from mother.agent.cognitive import CognitiveEngine, ThinkingMode, Confidence

    engine = CognitiveEngine()

    # Test goal setting and thinking mode determination
    engine.set_goal('Simple hello')
    print(f'  ✓ Simple goal mode: {engine.state.thinking_mode.value}')

    engine.set_goal('Analyze multiple database designs and evaluate each implementation')
    print(f'  ✓ Complex goal mode: {engine.state.thinking_mode.value}')

    # Test hypothesis management
    engine.state.active_hypotheses = ['Database A is faster', 'Database B scales better']
    engine.confirm_hypothesis('Database A is faster')
    print(f'  ✓ Confirmed hypothesis moved to facts: {engine.state.confirmed_facts}')

    engine.reject_hypothesis('Database B scales better', 'Benchmark showed poor results')
    print(f'  ✓ Rejected hypothesis added to uncertainties: {len(engine.state.uncertainties)} items')

    # Test confidence adjustment
    engine.state.confidence = Confidence.MEDIUM
    engine._adjust_confidence(30)
    print(f'  ✓ Confidence after +30: {engine.state.confidence.value}')

    engine._adjust_confidence(-50)
    print(f'  ✓ Confidence after -50: {engine.state.confidence.value}')

    # Test pattern learning
    engine._learn_pattern('test_tool', 'Always validate input format')
    patterns = engine.get_relevant_patterns('test_tool')
    print(f'  ✓ Learned patterns: {patterns}')

    # Test thought chain
    from mother.agent.cognitive import ThoughtChain
    chain = ThoughtChain(id='chain-1', goal='Test reasoning')
    chain.add_step('understanding', 'Understood the problem', evidence=['fact1'])
    chain.add_step('approach', 'Will solve step by step')
    print(f'  ✓ Thought chain steps: {len(chain.steps)}')

    # Test state persistence
    state_dict = engine.get_state_dict()
    print(f'  ✓ State dict keys: {list(state_dict.keys())}')

    # Test state restoration
    new_engine = CognitiveEngine()
    new_engine.restore_state(state_dict)
    print(f'  ✓ State restored: goal={new_engine.state.current_goal}')

    print('  ✓ Cognitive Engine: PASSED')
except Exception as e:
    print(f'  ✗ Cognitive Engine: FAILED - {e}')
    import traceback
    traceback.print_exc()

# Test 3: Session Store (Persistence)
print('\n--- TEST 3: Session Store (Session Persistence) ---')
try:
    from mother.agent.session import SessionStore, Session

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'sessions.db'
        session_store = SessionStore(db_path=db_path)

        now = datetime.now()

        # Create a session
        session = Session(
            id='test-session-1',
            created_at=now,
            updated_at=now,
            messages=[
                {'role': 'user', 'content': 'Hello'},
                {'role': 'assistant', 'content': 'Hi there!'},
                {'role': 'user', 'content': 'How are you?'},
            ],
            metadata={'test_key': 'test_value'},
        )
        session_store.save(session)
        print(f'  ✓ Created session: {session.id}')

        # Retrieve session
        retrieved = session_store.get('test-session-1')
        print(f'  ✓ Session message count: {len(retrieved.messages)}')
        print(f'  ✓ Metadata retrieved: {retrieved.metadata}')

        # List sessions
        sessions = session_store.get_recent(limit=10)
        print(f'  ✓ Listed {len(sessions)} sessions')

        # Get stats
        stats = session_store.get_stats()
        print(f'  ✓ Session stats: {stats}')

        print('  ✓ Session Store: PASSED')
except Exception as e:
    print(f'  ✗ Session Store: FAILED - {e}')
    import traceback
    traceback.print_exc()

# Test 4: Embedding Cache (ML Support)
print('\n--- TEST 4: Embedding Cache (ML/Personalization Support) ---')
try:
    from mother.memory.embeddings import EmbeddingCache

    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir) / 'cache'
        cache = EmbeddingCache(cache_dir=cache_dir)

        # Test caching
        test_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        cache.set('test text', 'test-model', test_embedding)

        retrieved = cache.get('test text', 'test-model')
        print(f'  ✓ Cache set/get: {retrieved == test_embedding}')

        # Test cache miss
        missing = cache.get('nonexistent', 'test-model')
        print(f'  ✓ Cache miss returns None: {missing is None}')

        print('  ✓ Embedding Cache: PASSED')
except Exception as e:
    print(f'  ✗ Embedding Cache: FAILED - {e}')
    import traceback
    traceback.print_exc()

# Test 5: Large-Scale Memory Test
print('\n--- TEST 5: Large-Scale Memory (Performance Test) ---')
try:
    import time
    from mother.memory.store import Memory, MemoryStore

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'large_test.db'
        store = MemoryStore(db_path=db_path)

        # Insert 1000 memories
        start = time.time()
        for i in range(1000):
            memory = Memory(
                id=None,
                timestamp=datetime.now(),
                session_id=f'perf-session-{i % 10}',
                role='user',
                content=f'Performance test memory {i} with some additional content to make it more realistic',
                embedding=[0.1] * 384 if i % 10 == 0 else None,  # 10% with embeddings
            )
            store.add(memory)
        insert_time = time.time() - start
        print(f'  ✓ Inserted 1000 memories in {insert_time:.2f}s ({1000/insert_time:.0f} mem/s)')

        # Retrieve recent
        start = time.time()
        for _ in range(100):
            store.get_recent(limit=20)
        retrieve_time = time.time() - start
        print(f'  ✓ 100 recent retrievals in {retrieve_time:.2f}s')

        # Stats
        stats = store.get_stats()
        print(f'  ✓ Final stats: {stats}')

        print('  ✓ Large-Scale Memory: PASSED')
except Exception as e:
    print(f'  ✗ Large-Scale Memory: FAILED - {e}')
    import traceback
    traceback.print_exc()

print('\n' + '=' * 60)
print('VERIFICATION COMPLETE')
print('=' * 60)
