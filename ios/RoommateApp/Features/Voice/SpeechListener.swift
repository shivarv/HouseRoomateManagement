import AVFoundation
import Observation
import Speech

/// Listens once: words appear as they're heard, and it stops by itself after a short pause (or
/// when `stop()` is called). Then `onFinish` gets everything that was heard ("" for nothing).
@MainActor
@Observable
final class SpeechListener {
    enum Problem: Equatable {
        case notAllowed  // mic or speech recognition turned off for the app
        case unavailable  // no recognizer for this language, or it's offline right now
    }

    private(set) var text = ""
    private(set) var isListening = false

    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var silence: Task<Void, Never>?
    private var onFinish: ((String) -> Void)?

    /// How long a pause ends it, and how long to wait for the first word.
    private static let pause: Duration = .seconds(1.6)
    private static let firstWord: Duration = .seconds(6)

    /// Asks for the mic and speech recognition (only the first time), then listens.
    /// Returns a problem instead when it can't.
    func start(onFinish: @escaping (String) -> Void) async -> Problem? {
        cancel()
        guard await Self.speechAllowed(), await AVAudioApplication.requestRecordPermission() else {
            return .notAllowed
        }
        guard let recognizer = SFSpeechRecognizer(locale: .current) ?? SFSpeechRecognizer(locale: Locale(identifier: "en-US")),
              recognizer.isAvailable else {
            return .unavailable
        }

        do {
            let audio = AVAudioSession.sharedInstance()
            try audio.setCategory(.record, mode: .measurement, options: .duckOthers)
            try audio.setActive(true, options: .notifyOthersOnDeactivation)

            let request = SFSpeechAudioBufferRecognitionRequest()
            request.shouldReportPartialResults = true
            if recognizer.supportsOnDeviceRecognition { request.requiresOnDeviceRecognition = true }

            let input = engine.inputNode
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0), block: Self.tap(request))
            engine.prepare()
            try engine.start()

            self.request = request
            self.onFinish = onFinish
            text = ""
            isListening = true
            task = recognizer.recognitionTask(with: request, resultHandler: Self.handler(self))
            waitForSilence(Self.firstWord)
            return nil
        } catch {
            teardown()
            return .unavailable
        }
    }

    /// Done talking: work out what was said.
    func stop() {
        guard isListening else { return }
        finish()
    }

    /// Closed or switched to typing: nothing is sent.
    func cancel() {
        onFinish = nil
        teardown()
    }

    // MARK: - Private

    private func heard(_ words: String?, final: Bool, failed: Bool) {
        guard isListening else { return }
        if let words, !words.isEmpty {
            text = words
            waitForSilence(Self.pause)
        }
        if final || failed { finish() }
    }

    /// Restarted on every new word: when it runs out, they've stopped talking.
    private func waitForSilence(_ wait: Duration) {
        silence?.cancel()
        silence = Task { [weak self] in
            try? await Task.sleep(for: wait)
            guard !Task.isCancelled else { return }
            self?.finish()
        }
    }

    private func finish() {
        let said = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let done = onFinish
        onFinish = nil
        teardown()
        done?(said)
    }

    private func teardown() {
        silence?.cancel()
        silence = nil
        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()
        request = nil
        task = nil
        isListening = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }

    // These run on audio / speech threads, so they're built outside the main actor.

    nonisolated private static func tap(_ request: SFSpeechAudioBufferRecognitionRequest) -> AVAudioNodeTapBlock {
        { buffer, _ in request.append(buffer) }
    }

    nonisolated private static func handler(_ listener: SpeechListener) -> (SFSpeechRecognitionResult?, Error?) -> Void {
        { [weak listener] result, error in
            let words = result?.bestTranscription.formattedString
            let final = result?.isFinal ?? false
            let failed = error != nil
            Task { @MainActor in listener?.heard(words, final: final, failed: failed) }
        }
    }

    nonisolated private static func speechAllowed() async -> Bool {
        await withCheckedContinuation { done in
            SFSpeechRecognizer.requestAuthorization { done.resume(returning: $0 == .authorized) }
        }
    }
}
