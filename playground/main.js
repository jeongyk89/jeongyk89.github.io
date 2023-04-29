const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

let audioContext;
let analyser;
let bufferLength;
let dataArray;

navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        analyser = audioContext.createAnalyser();
        source.connect(analyser);

        analyser.fftSize = 2048;
        bufferLength = analyser.frequencyBinCount;
        dataArray = new Uint8Array(bufferLength);
    })
    .catch(err => {
        console.error('Error accessing the microphone:', err);
    });

function draw() {
    requestAnimationFrame(draw);

    if (analyser) {
        analyser.getByteTimeDomainData(dataArray);
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < bufferLength; i++) {
        const value = dataArray[i] / 128;
        const y = canvas.height * 0.5 - value * canvas.height * 0.5;
        const x = canvas.width * i / bufferLength;

        ctx.beginPath();
        ctx.arc(x, y, 2, 0, 2 * Math.PI, false);
        ctx.fillStyle = `hsl(${i / bufferLength * 360}, 100%, 50%)`;
        ctx.fill();
    }
}

draw();
