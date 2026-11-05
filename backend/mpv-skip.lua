-- Home Base: a Skip intro / Skip credits button over a Plex video while the server's markers say one is on, taken
-- with the remote's OK. In the closing credits (the server's final marker) it reads Next episode when there is one,
-- and ends the video with exit code 10: watched to the end, go on to the next.
--
-- script-opts: homebase-markers = "intro 31.2 121.9;credits 1408.0 1420.0 final" (seconds), homebase-next = 1|0

local markers = {}
for spec in (mp.get_opt('homebase-markers') or ''):gmatch('[^;]+') do
    local kind, s, e, final = spec:match('^(%a+) ([%d.]+) ([%d.]+) ?(%a*)$')
    if kind then
        markers[#markers + 1] = { kind = kind, s = tonumber(s), e = tonumber(e), final = final == 'final' }
    end
end
local has_next = mp.get_opt('homebase-next') == '1'
if #markers == 0 then return end

local overlay = mp.create_osd_overlay('ass-events')
overlay.res_x, overlay.res_y = 1920, 1080
local current = nil

local function label(m)
    if m.kind == 'intro' then return 'Skip intro' end
    if m.final and has_next then return 'Next episode' end
    return 'Skip credits'
end

-- a white rounded box at the lower right, above where mpv's own controls appear
local W, H, R, RIGHT, BOTTOM = 380, 96, 18, 80, 150

local function box_path(w, h, r)
    return string.format('m %d 0 l %d 0 b %d 0 %d 0 %d %d l %d %d b %d %d %d %d %d %d l %d %d b 0 %d 0 %d 0 %d l 0 %d b 0 0 0 0 %d 0',
        r, w - r, w, w, w, r, w, h - r, w, h, w, h, w - r, h, r, h, h, h, h - r, r, r)
end

local function show(m)
    local x, y = 1920 - RIGHT - W, 1080 - BOTTOM - H
    overlay.data = string.format('{\\an7\\pos(%d,%d)\\bord0\\shad0\\1c&HFFFFFF&\\1a&H10&\\p1}%s{\\p0}\n' ..
        '{\\an5\\pos(%d,%d)\\bord0\\shad0\\1c&H1A1A1A&\\fs42\\b1}%s',
        x, y, box_path(W, H, R), x + W / 2, y + H / 2, label(m))
    overlay:update()
end

local function skip()
    local m = current
    if not m then return end
    if m.final then
        mp.command('quit 10')
    else
        mp.commandv('seek', tostring(m.e), 'absolute')
    end
end

local function set(m)
    if m == current then return end
    current = m
    if m then
        show(m)
        mp.add_forced_key_binding('ENTER', 'homebase-skip', skip)
        mp.add_forced_key_binding('KP_ENTER', 'homebase-skip-kp', skip)
    else
        overlay:remove()
        mp.remove_key_binding('homebase-skip')
        mp.remove_key_binding('homebase-skip-kp')
    end
end

mp.observe_property('time-pos', 'number', function(_, t)
    local found = nil
    if t then
        for _, m in ipairs(markers) do
            if t >= m.s and t < m.e - 0.5 then found = m break end
        end
    end
    set(found)
end)
