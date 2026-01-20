# OBS Studio Recording Guide for TradeUp Demo

## Quick Setup (5 minutes)

### Step 1: First Launch Settings

When OBS opens for the first time, it will run the **Auto-Configuration Wizard**. Choose:
- **Optimize for recording** (not streaming)
- **Resolution**: 1920x1080
- **FPS**: 60

### Step 2: Scene Setup

1. In the **Scenes** panel (bottom-left), you'll see a default scene
2. In the **Sources** panel (next to Scenes), click the **+** button
3. Select **Window Capture**
4. Name it "Chrome Browser"
5. In the dropdown, select your Chrome window showing TradeUp

### Step 3: Recording Settings

Go to **Settings** (bottom-right) > **Output**:

| Setting | Value |
|---------|-------|
| Output Mode | Simple |
| Recording Quality | High Quality, Medium File Size |
| Recording Format | mp4 |
| Encoder | Hardware (NVENC) if available, otherwise x264 |

Go to **Settings** > **Video**:

| Setting | Value |
|---------|-------|
| Base Resolution | 1920x1080 |
| Output Resolution | 1920x1080 |
| FPS | 60 |

### Step 4: Audio Settings (Important!)

Go to **Settings** > **Audio**:

| Setting | Value |
|---------|-------|
| Desktop Audio | Disabled |
| Mic/Auxiliary Audio | Disabled |

**Why disable audio?** We're recording silent footage and adding the ElevenLabs voiceover in CapCut later. This gives us more control over timing.

### Step 5: Hotkeys (Optional but Helpful)

Go to **Settings** > **Hotkeys**:
- **Start Recording**: Set to `Ctrl+Shift+R`
- **Stop Recording**: Set to `Ctrl+Shift+S`

---

## Recording Checklist

Before you hit record:

- [ ] Chrome window is maximized and showing TradeUp dashboard
- [ ] No bookmarks bar visible (press Ctrl+Shift+B to toggle)
- [ ] No other tabs visible
- [ ] Clean test data in the app (no embarrassing names)
- [ ] OBS preview shows the full Chrome window
- [ ] Audio sources are DISABLED (we add voiceover in post)

---

## Recording the Demo

### Scene-by-Scene Guide

Follow the script from `docs/DEMO_VIDEO_SCRIPT.md`. Here's the timing:

| Scene | Duration | What to Show |
|-------|----------|--------------|
| 1. Hook | 15 sec | Dashboard fade in, let it sit |
| 2. Dashboard | 30 sec | Hover over metrics, click Quick Actions area |
| 3. Tiers | 30 sec | Navigate to Settings/Tiers, show tier config |
| 4. Members | 30 sec | Navigate to Members, search, click a member |
| 5. Trade-In | 30 sec | Create new trade-in, add items, show Quick Flip |
| 6. Customer Portal | 20 sec | Navigate to /apps/rewards (customer view) |
| 7. CTA | 15 sec | Return to dashboard or show pricing |

**Total: ~2:50** (slightly longer than voiceover to give editing room)

### Recording Tips

1. **Move the mouse SLOWLY** - Fast movements look jerky
2. **Pause 2-3 seconds** at each major screen before clicking
3. **Let animations complete** before moving on
4. **Hover over elements** being discussed in voiceover
5. **Don't worry about mistakes** - we'll edit in CapCut

---

## After Recording

1. Click **Stop Recording** or press your hotkey
2. Recording saves to: `C:\Users\[YourName]\Videos\` by default
3. Open CapCut to combine video + voiceover

---

## Troubleshooting

### Black screen in preview?
- Try "Display Capture" instead of "Window Capture"
- Or run OBS as Administrator

### Chrome window not appearing in list?
- Make sure Chrome is open and visible
- Try "Display Capture" and crop to Chrome

### Recording is choppy?
- Lower FPS to 30
- Use "Indistinguishable Quality" instead of "High Quality"
- Close other programs

---

## File Locations

- **Voiceover**: `Downloads/ElevenLabs_*.mp3`
- **Recording**: `Videos/*.mp4` (or check OBS Settings > Output > Recording Path)
- **Script**: `docs/DEMO_VIDEO_SCRIPT.md`

---

*Guide created: January 19, 2026*
