def generate_workout(duration_minutes: int) -> str:
    """
    Generate a dynamic workout based on the specified duration.

    Args:
        duration_minutes (int): Total workout duration in minutes
        
    Returns:
        str: Formatted workout string
    """

    # Calculate time allocation (as percentages of total time)
    warmup_percent = 0.20  # 20% for warm-up
    cooldown_percent = 0.15  # 15% for cool-down
    main_percent = 0.65  # 65% for main workout

    # Calculate actual times
    warmup_time = max(3, int(duration_minutes * warmup_percent))  # Minimum 3 min
    cooldown_time = max(3, int(duration_minutes * cooldown_percent))  # Minimum 3 min
    main_time = duration_minutes - warmup_time - cooldown_time

    # Ensure main workout gets reasonable time
    if main_time < 5:
        warmup_time = 3
        cooldown_time = 2
        main_time = max(0, duration_minutes - 5)

    # Generate workout segments
    workout_parts = []

    # Warm-up
    workout_parts.append("**Warm-Up – {} minutes**".format(warmup_time))
    workout_parts.append("* {} min @ 4.0 mph (easy warm up)".format(warmup_time))

    # Main workout - split into intervals based on duration
    workout_parts.append("\n**Main Workout – {} minutes**".format(main_time))

    if main_time >= 15:
        # Longer workouts get more complex intervals
        steady_time = main_time // 2
        interval_time = main_time - steady_time
        tempo_segments = interval_time // 2
        
        workout_parts.append("* {} min @ 6.0 mph (steady pace)".format(steady_time))
        if tempo_segments > 0:
            workout_parts.append("* {} min @ 7.0 mph (tempo interval)".format(tempo_segments))
            remaining = interval_time - tempo_segments
            if remaining > 0:
                workout_parts.append("* {} min @ 6.0 mph (recovery)".format(remaining))
    else:
        # Shorter workouts are simpler
        workout_parts.append("* {} min @ 6.0 mph (steady pace)".format(main_time))

    # Cool-down
    workout_parts.append("\n**Cool-Down – {} minutes**".format(cooldown_time))
    workout_parts.append("* {} min @ 3.5 mph (easy cool down)".format(cooldown_time))

    return "\n".join(workout_parts)


if __name__ == "__main__":
    # Example usage for different durations
    durations = [20, 30, 40, 45, 60]
    print("Dynamic Workout Generator\n" + "=" * 50)
    for duration in durations:
        print(f"\n{duration} MINUTE WORKOUT:")
        print("-" * 30)
        print(generate_workout(duration))
        print()

