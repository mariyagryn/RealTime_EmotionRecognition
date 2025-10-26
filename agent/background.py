import time
from agent.capture import AsyncCamera
from agent.engine_fer import FastFerAnalyzer as EmotionAnalyzer
from storage.sessions import SessionWriter
from agent.state import is_paused

def run_background(loop_delay=0.02, cam_index=0, width=200, height=112, detector="opencv"):
    cam = AsyncCamera(index=cam_index, width=width, height=height)
    an  = EmotionAnalyzer(detector_backend=detector, alpha=0.3, scale_for_infer=0.4)
    sess = SessionWriter(kind="agent")

    fps, t_prev = 0.0, time.time()
    last_infer_t = 0.0
    ANALYZE_EVERY = 2.0
    noface_streak, backoff_extra = 0, 0.0
    last_print = 0.0

    print("[agent] Fast Mode (async capture). Ctrl+C to stop.")
    try:
        while True:
            frame = cam.latest()
            now = time.time()

            dt = now - t_prev; t_prev = now
            if dt > 0: fps = 0.9*fps + 0.1*(1.0/dt)

            if frame is not None and (now - last_infer_t) >= (ANALYZE_EVERY + backoff_extra):
                emo = an.infer(frame)
                last_infer_t = now

                if not emo["has_face"]:
                    noface_streak += 1
                    backoff_extra = min(2.0, 0.3 * noface_streak)
                else:
                    noface_streak, backoff_extra = 0, 0.0

                sess.append_event(emo, fps=fps)

                if now - last_print > 0.5:
                    print(f"[agent] {emo['dominant']:>7} {emo['conf']:.1f}% | loop {fps:,.1f}Hz | face={emo['has_face']} | +{backoff_extra:.1f}s")
                    last_print = now

            time.sleep(loop_delay)
            if is_paused():
                time.sleep(0.2)
                continue
    except KeyboardInterrupt:
        pass
    finally:
        cam.stop()
        path = sess.close()
        print("[agent] stopped. summary:", path)
ENGINE = "fer"
