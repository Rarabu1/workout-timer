"""
Test suite for The Treadmill Run Coach Backend Scaffold

Tests the acceptance criteria:
- Timer never resets to zero mid-run; only segment_elapsed_s resets
- Different input durations produce different workouts
- Same inputs + seed → identical plan; same inputs + different seed → different plan
- Regeneration after selection returns a new workout id; history remains
"""

import pytest
import time
from backend_scaffold import app, _WORKOUTS, _SESSIONS, _generate_segments
from fastapi.testclient import TestClient

client = TestClient(app)

class TestWorkoutGeneration:
    """Test workout generation and regeneration functionality"""
    
    def setup_method(self):
        """Clear stores before each test"""
        _WORKOUTS.clear()
        _SESSIONS.clear()
    
    def test_different_durations_produce_different_workouts(self):
        """Test that 30 vs 60 min workouts differ"""
        # Generate 30-minute workout
        inputs_30 = {"duration_min": 30}
        response_30 = client.post("/workouts/generate", json=inputs_30)
        assert response_30.status_code == 200
        workout_30 = response_30.json()
        
        # Generate 60-minute workout
        inputs_60 = {"duration_min": 60}
        response_60 = client.post("/workouts/generate", json=inputs_60)
        assert response_60.status_code == 200
        workout_60 = response_60.json()
        
        # Verify they're different
        assert workout_30["id"] != workout_60["id"]
        assert workout_30["stats"]["total_time_s"] == 1800  # 30 min
        assert workout_60["stats"]["total_time_s"] == 3600  # 60 min
        assert len(workout_30["segments"]) != len(workout_60["segments"])
    
    def test_same_inputs_same_seed_produces_identical_plan(self):
        """Test deterministic generation with same seed"""
        inputs = {"duration_min": 45, "seed": 12345}
        
        # Generate first workout
        response1 = client.post("/workouts/generate", json=inputs)
        assert response1.status_code == 200
        workout1 = response1.json()
        
        # Generate second workout with same inputs
        response2 = client.post("/workouts/generate", json=inputs)
        assert response2.status_code == 200
        workout2 = response2.json()
        
        # Verify they're identical (except id and created_at)
        assert workout1["id"] != workout2["id"]  # Different IDs
        assert workout1["seed"] == workout2["seed"] == 12345
        assert workout1["segments"] == workout2["segments"]  # Same segments
        assert workout1["stats"] == workout2["stats"]  # Same stats
    
    def test_same_inputs_different_seed_produces_different_plan(self):
        """Test that different seeds produce different plans"""
        inputs1 = {"duration_min": 45, "seed": 12345}
        inputs2 = {"duration_min": 45, "seed": 67890}
        
        # Generate workouts with different seeds
        response1 = client.post("/workouts/generate", json=inputs1)
        response2 = client.post("/workouts/generate", json=inputs2)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        workout1 = response1.json()
        workout2 = response2.json()
        
        # Verify they're different
        assert workout1["segments"] != workout2["segments"]
        assert workout1["seed"] != workout2["seed"]
    
    def test_regeneration_creates_new_workout_preserves_history(self):
        """Test regeneration creates new workout without overwriting history"""
        # Create initial workout
        inputs = {"duration_min": 30}
        response1 = client.post("/workouts/generate", json=inputs)
        assert response1.status_code == 200
        original_workout = response1.json()
        original_id = original_workout["id"]
        
        # Regenerate workout
        response2 = client.post(f"/workouts/{original_id}/regenerate")
        assert response2.status_code == 200
        new_workout = response2.json()
        new_id = new_workout["id"]
        
        # Verify new workout was created
        assert new_id != original_id
        
        # Verify original workout still exists
        response3 = client.get(f"/workouts/{original_id}")
        assert response3.status_code == 200
        assert response3.json()["id"] == original_id
        
        # Verify new workout exists
        response4 = client.get(f"/workouts/{new_id}")
        assert response4.status_code == 200
        assert response4.json()["id"] == new_id
    
    def test_get_workout_not_found(self):
        """Test 404 for non-existent workout"""
        response = client.get("/workouts/nonexistent-id")
        assert response.status_code == 404
    
    def test_regenerate_workout_not_found(self):
        """Test 404 for regenerating non-existent workout"""
        response = client.post("/workouts/nonexistent-id/regenerate")
        assert response.status_code == 404

class TestSessionManagement:
    """Test session creation and management"""
    
    def setup_method(self):
        """Clear stores and create a test workout"""
        _WORKOUTS.clear()
        _SESSIONS.clear()
        
        # Create a test workout
        inputs = {"duration_min": 30}
        response = client.post("/workouts/generate", json=inputs)
        assert response.status_code == 200
        self.workout_id = response.json()["id"]
    
    def test_create_session(self):
        """Test session creation"""
        response = client.post("/sessions", params={"workout_id": self.workout_id})
        assert response.status_code == 200
        
        session = response.json()
        assert session["workout_id"] == self.workout_id
        assert session["status"] == "idle"
        assert session["elapsed_s"] == 0
        assert session["segment_elapsed_s"] == 0
        assert session["current_segment_index"] == 0
    
    def test_create_session_invalid_workout(self):
        """Test session creation with invalid workout ID"""
        response = client.post("/sessions", params={"workout_id": "invalid-id"})
        assert response.status_code == 404

class TestTimerBehavior:
    """Test timer behavior and session state management"""
    
    def setup_method(self):
        """Clear stores and create a test workout and session"""
        _WORKOUTS.clear()
        _SESSIONS.clear()
        
        # Create a test workout with short segments for testing
        inputs = {"duration_min": 5}  # 5 minutes for faster testing
        response = client.post("/workouts/generate", json=inputs)
        assert response.status_code == 200
        self.workout_id = response.json()["id"]
        
        # Create a session
        response = client.post("/sessions", params={"workout_id": self.workout_id})
        assert response.status_code == 200
        self.session_id = response.json()["id"]
    
    def test_timer_continuous_elapsed_no_reset(self):
        """Test that elapsed_s never resets during a run"""
        # Start session
        response = client.post(f"/sessions/{self.session_id}/start")
        assert response.status_code == 200
        
        # Wait a bit
        time.sleep(0.2)
        
        # Check state
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        state1 = response.json()
        elapsed1 = state1["elapsed_s"]
        assert elapsed1 > 0
        
        # Wait more
        time.sleep(0.2)
        
        # Check state again
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        state2 = response.json()
        elapsed2 = state2["elapsed_s"]
        
        # Verify elapsed time only increases
        assert elapsed2 > elapsed1
        
        # Pause and resume
        response = client.post(f"/sessions/{self.session_id}/pause")
        assert response.status_code == 200
        
        response = client.post(f"/sessions/{self.session_id}/resume")
        assert response.status_code == 200
        
        # Wait more
        time.sleep(0.2)
        
        # Check state again
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        state3 = response.json()
        elapsed3 = state3["elapsed_s"]
        
        # Verify elapsed time continues to increase (no reset)
        assert elapsed3 > elapsed2
    
    def test_segment_elapsed_resets_on_segment_change(self):
        """Test that segment_elapsed_s resets when segments change"""
        # Start session
        response = client.post(f"/sessions/{self.session_id}/start")
        assert response.status_code == 200
        
        # Get initial state
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        initial_state = response.json()
        initial_segment = initial_state["current_segment_index"]
        initial_segment_elapsed = initial_state["segment_elapsed_s"]
        
        # Skip to next segment
        response = client.post(f"/sessions/{self.session_id}/skip")
        assert response.status_code == 200
        
        # Check state
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        new_state = response.json()
        
        # Verify segment changed and segment_elapsed reset
        assert new_state["current_segment_index"] == initial_segment + 1
        assert new_state["segment_elapsed_s"] < 0.1  # Small amount of time may have passed
        
        # Verify total elapsed continued
        assert new_state["elapsed_s"] >= initial_state["elapsed_s"]
    
    def test_session_completion(self):
        """Test session completion when all segments are done"""
        # Start session
        response = client.post(f"/sessions/{self.session_id}/start")
        assert response.status_code == 200
        
        # Skip through all segments
        workout = _WORKOUTS[self.workout_id]
        num_segments = len(workout.segments)
        
        for _ in range(num_segments):
            response = client.post(f"/sessions/{self.session_id}/skip")
            assert response.status_code == 200
        
        # Check final state
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        final_state = response.json()
        
        # Verify session is completed
        assert final_state["status"] == "completed"
        assert final_state["current_segment_index"] >= num_segments
    
    def test_back_segment(self):
        """Test going back to previous segment"""
        # Start session
        response = client.post(f"/sessions/{self.session_id}/start")
        assert response.status_code == 200
        
        # Skip to next segment
        response = client.post(f"/sessions/{self.session_id}/skip")
        assert response.status_code == 200
        
        # Check we're on segment 1
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        state = response.json()
        assert state["current_segment_index"] == 1
        
        # Go back
        response = client.post(f"/sessions/{self.session_id}/back")
        assert response.status_code == 200
        
        # Check we're back on segment 0
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        state = response.json()
        assert state["current_segment_index"] == 0
        assert state["segment_elapsed_s"] < 0.1  # Small amount of time may have passed
    
    def test_back_segment_at_beginning(self):
        """Test going back when already at first segment"""
        # Start session
        response = client.post(f"/sessions/{self.session_id}/start")
        assert response.status_code == 200
        
        # Try to go back
        response = client.post(f"/sessions/{self.session_id}/back")
        assert response.status_code == 200
        
        # Check we're still on segment 0
        response = client.get(f"/sessions/{self.session_id}")
        assert response.status_code == 200
        state = response.json()
        assert state["current_segment_index"] == 0

class TestErrorHandling:
    """Test error handling for invalid operations"""
    
    def setup_method(self):
        """Clear stores"""
        _WORKOUTS.clear()
        _SESSIONS.clear()
    
    def test_session_operations_on_nonexistent_session(self):
        """Test operations on non-existent session"""
        session_id = "nonexistent-session"
        
        # Test all session operations
        operations = ["start", "pause", "resume", "skip", "back"]
        for op in operations:
            response = client.post(f"/sessions/{session_id}/{op}")
            assert response.status_code == 404
        
        # Test get state
        response = client.get(f"/sessions/{session_id}")
        assert response.status_code == 404

class TestSegmentGeneration:
    """Test the segment generation logic directly"""
    
    def test_generate_segments_deterministic(self):
        """Test that segment generation is deterministic with same seed"""
        total_s = 1800  # 30 minutes
        seed = 12345
        
        segments1 = _generate_segments(total_s, seed)
        segments2 = _generate_segments(total_s, seed)
        
        # Verify identical segments
        assert len(segments1) == len(segments2)
        for s1, s2 in zip(segments1, segments2):
            assert s1.duration_s == s2.duration_s
            assert s1.speed_mph == s2.speed_mph
            assert s1.incline_pct == s2.incline_pct
            assert s1.label == s2.label
    
    def test_generate_segments_different_seeds(self):
        """Test that different seeds produce different segments"""
        total_s = 1800  # 30 minutes
        
        segments1 = _generate_segments(total_s, 12345)
        segments2 = _generate_segments(total_s, 67890)
        
        # Verify different segments (at least some differences)
        assert segments1 != segments2
    
    def test_generate_segments_total_duration(self):
        """Test that generated segments sum to approximately total duration"""
        total_s = 1800  # 30 minutes
        seed = 12345
        
        segments = _generate_segments(total_s, seed)
        total_generated = sum(s.duration_s for s in segments)
        
        # Should be close to total_s (within 10% tolerance)
        assert abs(total_generated - total_s) <= total_s * 0.1
    
    def test_generate_segments_structure(self):
        """Test that generated segments have proper structure"""
        total_s = 1800  # 30 minutes
        seed = 12345
        
        segments = _generate_segments(total_s, seed)
        
        # Should have at least warmup and cooldown
        labels = [s.label for s in segments]
        assert "warmup" in labels
        assert "cooldown" in labels
        
        # Should have proper indexing
        for i, segment in enumerate(segments):
            assert segment.index == i
        
        # Should have reasonable speeds and inclines
        for segment in segments:
            assert 3.0 <= segment.speed_mph <= 8.0
            assert 0 <= segment.incline_pct <= 5.0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
