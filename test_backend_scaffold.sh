#!/bin/bash

# Test script for The Treadmill Run Coach Backend Scaffold
# Make sure the server is running on http://localhost:8080

BASE_URL="http://localhost:8080"
echo "🧪 Testing Treadmill Run Coach Backend Scaffold"
echo "================================================"
echo "Base URL: $BASE_URL"
echo ""

# Test 1: Generate a workout
echo "📋 Test 1: Generate a 30-minute workout"
echo "----------------------------------------"
WORKOUT_RESPONSE=$(curl -s -X POST "$BASE_URL/workouts/generate" \
  -H "Content-Type: application/json" \
  -d '{"duration_min": 30, "seed": 12345}')
echo "Response: $WORKOUT_RESPONSE"

# Extract workout ID
WORKOUT_ID=$(echo $WORKOUT_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
echo "Workout ID: $WORKOUT_ID"
echo ""

# Test 2: Get the workout
echo "📋 Test 2: Get workout details"
echo "-------------------------------"
curl -s -X GET "$BASE_URL/workouts/$WORKOUT_ID" | jq '.'
echo ""

# Test 3: Create a session
echo "📋 Test 3: Create a session"
echo "----------------------------"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/sessions?workout_id=$WORKOUT_ID")
echo "Response: $SESSION_RESPONSE"

# Extract session ID
SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"id":"[^"]*"' | cut -d'"' -f4)
echo "Session ID: $SESSION_ID"
echo ""

# Test 4: Get initial session state
echo "📋 Test 4: Get initial session state"
echo "------------------------------------"
curl -s -X GET "$BASE_URL/sessions/$SESSION_ID" | jq '.'
echo ""

# Test 5: Start the session
echo "📋 Test 5: Start the session"
echo "----------------------------"
curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/start" | jq '.'
echo ""

# Wait a moment for timer to advance
echo "⏱️  Waiting 2 seconds for timer to advance..."
sleep 2

# Test 6: Get session state after starting
echo "📋 Test 6: Get session state after starting"
echo "-------------------------------------------"
curl -s -X GET "$BASE_URL/sessions/$SESSION_ID" | jq '.'
echo ""

# Test 7: Skip to next segment
echo "📋 Test 7: Skip to next segment"
echo "-------------------------------"
curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/skip" | jq '.'
echo ""

# Test 8: Pause the session
echo "📋 Test 8: Pause the session"
echo "----------------------------"
curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/pause" | jq '.'
echo ""

# Test 9: Resume the session
echo "📋 Test 9: Resume the session"
echo "-----------------------------"
curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/resume" | jq '.'
echo ""

# Test 10: Go back to previous segment
echo "📋 Test 10: Go back to previous segment"
echo "---------------------------------------"
curl -s -X POST "$BASE_URL/sessions/$SESSION_ID/back" | jq '.'
echo ""

# Test 11: Generate a different workout (60 minutes)
echo "📋 Test 11: Generate a 60-minute workout"
echo "----------------------------------------"
curl -s -X POST "$BASE_URL/workouts/generate" \
  -H "Content-Type: application/json" \
  -d '{"duration_min": 60, "seed": 67890}' | jq '.'
echo ""

# Test 12: Regenerate the original workout
echo "📋 Test 12: Regenerate the original workout"
echo "------------------------------------------"
curl -s -X POST "$BASE_URL/workouts/$WORKOUT_ID/regenerate" | jq '.'
echo ""

# Test 13: Test error handling - invalid session
echo "📋 Test 13: Test error handling - invalid session"
echo "------------------------------------------------"
curl -s -X GET "$BASE_URL/sessions/invalid-session-id"
echo ""

echo "✅ All tests completed!"
echo "🎯 Check the responses above to verify the API is working correctly."
echo "📖 Visit http://localhost:8080/docs for interactive API documentation."
