



SRC=derf/all/Johnny_1280x720_60.y4m

johnny.1280x720.60fps.264.mp4: ${SRC}
	ffmpeg -i $^ -c:v libx264 -preset slow -crf 18 $@
