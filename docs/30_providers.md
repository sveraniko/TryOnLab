\# Providers



\## Задача

Единый интерфейс для разных AI-провайдеров: изображения (try-on) и видео (presets).



\## ProviderBase (контракт)

Методы:

\- generate\_image(job: Job, inputs: ImageInputs, prompt: PromptPack) -> ProviderResult

\- generate\_video(job: Job, image: GeneratedImage, prompt: VideoPrompt) -> ProviderResult

\- capabilities -> {image\_edit: bool, video: bool, async\_video: bool}



Ошибки:

\- ProviderAuthError

\- ProviderRateLimitError

\- ProviderBadRequestError

\- ProviderTemporaryError



\## Grok (xAI)

\### Images

\- Endpoint: /v1/images/generations

\- Model: grok-imagine-image

\- Input: prompt + (опц.) image(s)

(см. xAI docs)



\### Video

\- Endpoint: POST /v1/videos/generations -> request\_id

\- Poll: GET /v1/videos/{request\_id} -> status(done|pending|expired) -> video.url

\- Model: grok-imagine-video

\- Videos are returned as temporary URLs (download promptly)



\## OpenAI

\### Images

\- /v1/images/edits или /v1/images/generations (в зависимости от режима)

\### Video (Sora)

\- Endpoint: /v1/videos

\- Model: sora-2 (или sora-2-YYYY-MM-DD snapshot)

\- Pricing/tiers/rate limits — см. docs



\## Provider selection (runtime)

\- AI\_PROVIDER\_DEFAULT: default provider for new users

\- User setting stored in DB: user.provider

\- Inline toggle in bot: \[Grok] \[OpenAI]

\- Allowlist to disable providers in prod quickly

