<script lang="ts">
	import { toast } from 'svelte-sonner';

	import { onMount, getContext, createEventDispatcher } from 'svelte';

	const dispatch = createEventDispatcher();

	import {
		getQuerySettings,
		updateQuerySettings,
		resetVectorDB,
		getEmbeddingConfig,
		updateEmbeddingConfig,
		getRerankingConfig,
		updateRerankingConfig,
		resetUploadDir,
		getRAGConfig,
		updateRAGConfig
	} from '$lib/apis/retrieval';

	import { knowledge, models } from '$lib/stores';
	import { getKnowledgeBases } from '$lib/apis/knowledge';
	import { uploadDir, deleteAllFiles, deleteFileById } from '$lib/apis/files';

	import ResetUploadDirConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import ResetVectorDBConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';
	import SensitiveInput from '$lib/components/common/SensitiveInput.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Switch from '$lib/components/common/Switch.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';

	const i18n = getContext('i18n');

	let scanDirLoading = false;
	let updateEmbeddingModelLoading = false;
	let updateRerankingModelLoading = false;

	let showResetConfirm = false;
	let showResetUploadDirConfirm = false;

	let embeddingEngine = '';
	let embeddingModel = '';
	let embeddingBatchSize = 1;
	let rerankingModel = '';

	let fileMaxSize = null;
	let fileMaxCount = null;

	let contentExtractionEngine = 'default';
	let tikaServerUrl = '';
	let showTikaServerUrl = false;
	let doclingServerUrl = '';
	let showDoclingServerUrl = false;
	let documentIntelligenceEndpoint = '';
	let documentIntelligenceKey = '';
	let showDocumentIntelligenceConfig = false;

	let textSplitter = '';
	let chunkSize = 0;
	let chunkOverlap = 0;
	let pdfExtractImages = true;

	let RAG_FULL_CONTEXT = false;
	let BYPASS_EMBEDDING_AND_RETRIEVAL = false;

	let enableGoogleDriveIntegration = false;
	let enableOneDriveIntegration = false;

	let OpenAIUrl = '';
	let OpenAIK = ''; // OpenAIKey

	let OllamaUrl = '';
	let OllamaK = ''; // OllamaKey

	let querySettings = {
		template: '',
		r: 0.0,
		k: 4,
		k_reranker: 4,
		hybrid: false
	};

	const embeddingModelUpdateHandler = async () => {
		if (embeddingEngine === '' && embeddingModel.split('/').length - 1 > 1) {
			toast.error(
				$i18n.t(
					'Model filesystem path detected. Model shortname is required for update, cannot continue.'
				)
			);
			return;
		}
		if (embeddingEngine === 'ollama' && embeddingModel === '') {
			toast.error(
				$i18n.t(
					'Model filesystem path detected. Model shortname is required for update, cannot continue.'
				)
			);
			return;
		}

		if (embeddingEngine === 'openai' && embeddingModel === '') {
			toast.error(
				$i18n.t(
					'Model filesystem path detected. Model shortname is required for update, cannot continue.'
				)
			);
			return;
		}

		if ((embeddingEngine === 'openai' && OpenAIK === '') || OpenAIUrl === '') {
			toast.error($i18n.t('OpenAI URL/Key required.'));
			return;
		}

		console.log('Update embedding model attempt:', embeddingModel);

		updateEmbeddingModelLoading = true;
		const res = await updateEmbeddingConfig(localStorage.token, {
			embedding_engine: embeddingEngine,
			embedding_model: embeddingModel,
			embedding_batch_size: embeddingBatchSize,
			ollama_config: {
				key: OllamaK,
				url: OllamaUrl
			},
			openai_config: {
				key: OpenAIK,
				url: OpenAIUrl
			}
		}).catch(async (error) => {
			toast.error(`${error}`);
			await setEmbeddingConfig();
			return null;
		});
		updateEmbeddingModelLoading = false;

		if (res) {
			console.log('embeddingModelUpdateHandler:', res);
			if (res.status === true) {
				toast.success($i18n.t('Embedding model set to "{{embedding_model}}"', res), {
					duration: 1000 * 10
				});
			}
		}
	};

	const rerankingModelUpdateHandler = async () => {
		console.log('Update reranking model attempt:', rerankingModel);

		updateRerankingModelLoading = true;
		const res = await updateRerankingConfig(localStorage.token, {
			reranking_model: rerankingModel
		}).catch(async (error) => {
			toast.error(`${error}`);
			await setRerankingConfig();
			return null;
		});
		updateRerankingModelLoading = false;

		if (res) {
			console.log('rerankingModelUpdateHandler:', res);
			if (res.status === true) {
				if (rerankingModel === '') {
					toast.success($i18n.t('Reranking model disabled', res), {
						duration: 1000 * 10
					});
				} else {
					toast.success($i18n.t('Reranking model set to "{{reranking_model}}"', res), {
						duration: 1000 * 10
					});
				}
			}
		}
	};

	const submitHandler = async () => {
		if (contentExtractionEngine === 'tika' && tikaServerUrl === '') {
			toast.error($i18n.t('Tika Server URL required.'));
			return;
		}
		if (contentExtractionEngine === 'docling' && doclingServerUrl === '') {
			toast.error($i18n.t('Docling Server URL required.'));
			return;
		}
		if (
			contentExtractionEngine === 'document_intelligence' &&
			(documentIntelligenceEndpoint === '' || documentIntelligenceKey === '')
		) {
			toast.error($i18n.t('Document Intelligence endpoint and key required.'));
			return;
		}

		if (!BYPASS_EMBEDDING_AND_RETRIEVAL) {
			await embeddingModelUpdateHandler();

			if (querySettings.hybrid) {
				await rerankingModelUpdateHandler();
			}
		}

		const res = await updateRAGConfig(localStorage.token, {
			pdf_extract_images: pdfExtractImages,
			enable_google_drive_integration: enableGoogleDriveIntegration,
			enable_onedrive_integration: enableOneDriveIntegration,
			file: {
				max_size: fileMaxSize === '' ? null : fileMaxSize,
				max_count: fileMaxCount === '' ? null : fileMaxCount
			},
			RAG_FULL_CONTEXT: RAG_FULL_CONTEXT,
			BYPASS_EMBEDDING_AND_RETRIEVAL: BYPASS_EMBEDDING_AND_RETRIEVAL,
			chunk: {
				text_splitter: textSplitter,
				chunk_overlap: chunkOverlap,
				chunk_size: chunkSize
			},
			content_extraction: {
				engine: contentExtractionEngine,
				tika_server_url: tikaServerUrl,
				docling_server_url: doclingServerUrl,
				document_intelligence_config: {
					key: documentIntelligenceKey,
					endpoint: documentIntelligenceEndpoint
				}
			}
		});

		await updateQuerySettings(localStorage.token, querySettings);

		dispatch('save');
	};

	const setEmbeddingConfig = async () => {
		const embeddingConfig = await getEmbeddingConfig(localStorage.token);

		if (embeddingConfig) {
			embeddingEngine = embeddingConfig.embedding_engine;
			embeddingModel = embeddingConfig.embedding_model;
			embeddingBatchSize = embeddingConfig.embedding_batch_size ?? 1;

			OpenAIK = embeddingConfig.openai_config.key;
			OpenAIUrl = embeddingConfig.openai_config.url;

			OllamaK = embeddingConfig.ollama_config.key;
			OllamaUrl = embeddingConfig.ollama_config.url;
		}
	};

	const setRerankingConfig = async () => {
		const rerankingConfig = await getRerankingConfig(localStorage.token);

		if (rerankingConfig) {
			rerankingModel = rerankingConfig.reranking_model;
		}
	};

	const toggleHybridSearch = async () => {
		querySettings = await updateQuerySettings(localStorage.token, querySettings);
	};

	onMount(async () => {
		await setEmbeddingConfig();
		await setRerankingConfig();

		querySettings = await getQuerySettings(localStorage.token);

		const res = await getRAGConfig(localStorage.token);

		if (res) {
			pdfExtractImages = res.pdf_extract_images;

			textSplitter = res.chunk.text_splitter;
			chunkSize = res.chunk.chunk_size;
			chunkOverlap = res.chunk.chunk_overlap;

			RAG_FULL_CONTEXT = res.RAG_FULL_CONTEXT;
			BYPASS_EMBEDDING_AND_RETRIEVAL = res.BYPASS_EMBEDDING_AND_RETRIEVAL;

			contentExtractionEngine = res.content_extraction.engine;
			tikaServerUrl = res.content_extraction.tika_server_url;
			doclingServerUrl = res.content_extraction.docling_server_url;

			showTikaServerUrl = contentExtractionEngine === 'tika';
			showDoclingServerUrl = contentExtractionEngine === 'docling';
			documentIntelligenceEndpoint = res.content_extraction.document_intelligence_config.endpoint;
			documentIntelligenceKey = res.content_extraction.document_intelligence_config.key;
			showDocumentIntelligenceConfig = contentExtractionEngine === 'document_intelligence';

			fileMaxSize = res?.file.max_size ?? '';
			fileMaxCount = res?.file.max_count ?? '';

			enableGoogleDriveIntegration = res.enable_google_drive_integration;
			enableOneDriveIntegration = res.enable_onedrive_integration;
		}
	});
</script>

<ResetUploadDirConfirmDialog
	bind:show={showResetUploadDirConfirm}
	on:confirm={async () => {
		const res = await deleteAllFiles(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Success'));
		}
	}}
/>

<ResetVectorDBConfirmDialog
	bind:show={showResetConfirm}
	on:confirm={() => {
		const res = resetVectorDB(localStorage.token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Success'));
		}
	}}
/>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={() => {
		submitHandler();
	}}
>
	<div class=" space-y-2.5 overflow-y-scroll scrollbar-hidden h-full pr-1.5">
		<div class="">
			<div class="mb-3">
				<div class=" mb-2.5 text-base font-medium">{$i18n.t('General')}</div>

				<hr class=" border-gray-100 dark:border-gray-850 my-2" />

				<div class="  mb-2.5 flex flex-col w-full justify-between">
					<div class="flex w-full justify-between">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('Content Extraction Engine')}
						</div>

						<div class="">
							<select
								class="dark:bg-gray-900 w-fit pr-8 rounded-sm px-2 text-xs bg-transparent outline-hidden text-right"
								bind:value={contentExtractionEngine}
							>
								<option value="">{$i18n.t('Default')} </option>
								<option value="tika">{$i18n.t('Tika')}</option>
								<option value="docling">{$i18n.t('Docling')}</option>
								<option value="document_intelligence">{$i18n.t('Document Intelligence')}</option>
							</select>
						</div>
					</div>
					{#if contentExtractionEngine === 'tika'}
						<div class="flex w-full mt-1">
							<div class="flex-1 mr-2">
								<input
									class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
									placeholder={$i18n.t('Enter Tika Server URL')}
									bind:value={tikaServerUrl}
								/>
							</div>
						</div>
					{:else if contentExtractionEngine === 'docling'}
						<div class="flex w-full mt-1">
							<input
								class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
								placeholder={$i18n.t('Enter Docling Server URL')}
								bind:value={doclingServerUrl}
							/>
						</div>
					{:else if contentExtractionEngine === 'document_intelligence'}
						<div class="my-0.5 flex gap-2 pr-2">
							<input
								class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
								placeholder={$i18n.t('Enter Document Intelligence Endpoint')}
								bind:value={documentIntelligenceEndpoint}
							/>

							<SensitiveInput
								placeholder={$i18n.t('Enter Document Intelligence Key')}
								bind:value={documentIntelligenceKey}
							/>
						</div>
					{/if}
				</div>

				{#if contentExtractionEngine === ''}
					<div class="  mb-2.5 flex w-full justify-between">
						<div class=" self-center text-xs font-medium">
							{$i18n.t('PDF Extract Images (OCR)')}
						</div>
						<div class="flex items-center relative">
							<Switch bind:state={pdfExtractImages} />
						</div>
					</div>
				{/if}

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">
						<Tooltip content={$i18n.t('Full Context Mode')} placement="top-start">
							{$i18n.t('Bypass Embedding and Retrieval')}
						</Tooltip>
					</div>
					<div class="flex items-center relative">
						<Tooltip
							content={BYPASS_EMBEDDING_AND_RETRIEVAL
								? $i18n.t(
										'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
									)
								: $i18n.t(
										'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
									)}
						>
							<Switch bind:state={BYPASS_EMBEDDING_AND_RETRIEVAL} />
						</Tooltip>
					</div>
				</div>

				{#if !BYPASS_EMBEDDING_AND_RETRIEVAL}
					<div class="  mb-2.5 flex w-full justify-between">
						<div class=" self-center text-xs font-medium">{$i18n.t('Text Splitter')}</div>
						<div class="flex items-center relative">
							<select
								class="dark:bg-gray-900 w-fit pr-8 rounded-sm px-2 text-xs bg-transparent outline-hidden text-right"
								bind:value={textSplitter}
							>
								<option value="">{$i18n.t('Default')} ({$i18n.t('Character')})</option>
								<option value="token">{$i18n.t('Token')} ({$i18n.t('Tiktoken')})</option>
							</select>
						</div>
					</div>

					<div class="  mb-2.5 flex w-full justify-between">
						<div class=" flex gap-1.5 w-full">
							<div class="  w-full justify-between">
								<div class="self-center text-xs font-medium min-w-fit mb-1">
									{$i18n.t('Chunk Size')}
								</div>
								<div class="self-center">
									<input
										class=" w-full rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
										type="number"
										placeholder={$i18n.t('Enter Chunk Size')}
										bind:value={chunkSize}
										autocomplete="off"
										min="0"
									/>
								</div>
							</div>

							<div class="w-full">
								<div class=" self-center text-xs font-medium min-w-fit mb-1">
									{$i18n.t('Chunk Overlap')}
								</div>

								<div class="self-center">
									<input
										class="w-full rounded-lg py-1.5 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850 outline-hidden"
										type="number"
										placeholder={$i18n.t('Enter Chunk Overlap')}
										bind:value={chunkOverlap}
										autocomplete="off"
										min="0"
									/>
								</div>
							</div>
						</div>
					</div>
				{/if}
			</div>

			{#if !BYPASS_EMBEDDING_AND_RETRIEVAL}
				<div class="mb-3">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('Embedding')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<div class="  mb-2.5 flex flex-col w-full justify-between">
						<div class="flex w-full justify-between">
							<div class=" self-center text-xs font-medium">
								{$i18n.t('Embedding Model Engine')}
							</div>
							<div class="flex items-center relative">
								<select
									class="dark:bg-gray-900 w-fit pr-8 rounded-sm px-2 p-1 text-xs bg-transparent outline-hidden text-right"
									bind:value={embeddingEngine}
									placeholder="Select an embedding model engine"
									on:change={(e) => {
										if (e.target.value === 'ollama') {
											embeddingModel = '';
										} else if (e.target.value === 'openai') {
											embeddingModel = 'text-embedding-3-small';
										} else if (e.target.value === '') {
											embeddingModel = 'sentence-transformers/all-MiniLM-L6-v2';
										}
									}}
								>
									<option value="">{$i18n.t('Default (SentenceTransformers)')}</option>
									<option value="ollama">{$i18n.t('Ollama')}</option>
									<option value="openai">{$i18n.t('OpenAI')}</option>
								</select>
							</div>
						</div>

						{#if embeddingEngine === 'openai'}
							<div class="my-0.5 flex gap-2 pr-2">
								<input
									class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
									placeholder={$i18n.t('API Base URL')}
									bind:value={OpenAIUrl}
									required
								/>

								<SensitiveInput placeholder={$i18n.t('API Key')} bind:value={OpenAIK} />
							</div>
						{:else if embeddingEngine === 'ollama'}
							<div class="my-0.5 flex gap-2 pr-2">
								<input
									class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
									placeholder={$i18n.t('API Base URL')}
									bind:value={OllamaUrl}
									required
								/>

								<SensitiveInput
									placeholder={$i18n.t('API Key')}
									bind:value={OllamaK}
									required={false}
								/>
							</div>
						{/if}
					</div>

					<div class="  mb-2.5 flex flex-col w-full">
						<div class=" mb-1 text-xs font-medium">{$i18n.t('Embedding Model')}</div>

						<div class="">
							{#if embeddingEngine === 'ollama'}
								<div class="flex w-full">
									<div class="flex-1 mr-2">
										<input
											class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
											bind:value={embeddingModel}
											placeholder={$i18n.t('Set embedding model')}
											required
										/>
									</div>
								</div>
							{:else}
								<div class="flex w-full">
									<div class="flex-1 mr-2">
										<input
											class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
											placeholder={$i18n.t('Set embedding model (e.g. {{model}})', {
												model: embeddingModel.slice(-40)
											})}
											bind:value={embeddingModel}
										/>
									</div>

									{#if embeddingEngine === ''}
										<button
											class="px-2.5 bg-transparent text-gray-800 dark:bg-transparent dark:text-gray-100 rounded-lg transition"
											on:click={() => {
												embeddingModelUpdateHandler();
											}}
											disabled={updateEmbeddingModelLoading}
										>
											{#if updateEmbeddingModelLoading}
												<div class="self-center">
													<svg
														class=" w-4 h-4"
														viewBox="0 0 24 24"
														fill="currentColor"
														xmlns="http://www.w3.org/2000/svg"
													>
														<style>
															.spinner_ajPY {
																transform-origin: center;
																animation: spinner_AtaB 0.75s infinite linear;
															}

															@keyframes spinner_AtaB {
																100% {
																	transform: rotate(360deg);
																}
															}
														</style>
														<path
															d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
															opacity=".25"
														/>
														<path
															d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
															class="spinner_ajPY"
														/>
													</svg>
												</div>
											{:else}
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 16 16"
													fill="currentColor"
													class="w-4 h-4"
												>
													<path
														d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z"
													/>
													<path
														d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z"
													/>
												</svg>
											{/if}
										</button>
									{/if}
								</div>
							{/if}
						</div>

						<div class="mt-1 mb-1 text-xs text-gray-400 dark:text-gray-500">
							{$i18n.t(
								'Warning: If you update or change your embedding model, you will need to re-import all documents.'
							)}
						</div>
					</div>

					{#if embeddingEngine === 'ollama' || embeddingEngine === 'openai'}
						<div class="  mb-2.5 flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Embedding Batch Size')}</div>

							<div class="">
								<input
									bind:value={embeddingBatchSize}
									type="number"
									class=" bg-transparent text-center w-14 outline-none"
									min="-2"
									max="16000"
									step="1"
								/>
							</div>
						</div>
					{/if}
				</div>

				<div class="mb-3">
					<div class=" mb-2.5 text-base font-medium">{$i18n.t('Retrieval')}</div>

					<hr class=" border-gray-100 dark:border-gray-850 my-2" />

					<div class="  mb-2.5 flex w-full justify-between">
						<div class=" self-center text-xs font-medium">{$i18n.t('Full Context Mode')}</div>
						<div class="flex items-center relative">
							<Tooltip
								content={RAG_FULL_CONTEXT
									? $i18n.t(
											'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
										)
									: $i18n.t(
											'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
										)}
							>
								<Switch bind:state={RAG_FULL_CONTEXT} />
							</Tooltip>
						</div>
					</div>

					{#if !RAG_FULL_CONTEXT}
						<div class="  mb-2.5 flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Hybrid Search')}</div>
							<div class="flex items-center relative">
								<Switch
									bind:state={querySettings.hybrid}
									on:change={() => {
										toggleHybridSearch();
									}}
								/>
							</div>
						</div>

						{#if querySettings.hybrid === true}
							<div class="  mb-2.5 flex flex-col w-full">
								<div class=" mb-1 text-xs font-medium">{$i18n.t('Reranking Model')}</div>

								<div class="">
									<div class="flex w-full">
										<div class="flex-1 mr-2">
											<input
												class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
												placeholder={$i18n.t('Set reranking model (e.g. {{model}})', {
													model: 'BAAI/bge-reranker-v2-m3'
												})}
												bind:value={rerankingModel}
											/>
										</div>
										<button
											class="px-2.5 bg-transparent text-gray-800 dark:bg-transparent dark:text-gray-100 rounded-lg transition"
											on:click={() => {
												rerankingModelUpdateHandler();
											}}
											disabled={updateRerankingModelLoading}
										>
											{#if updateRerankingModelLoading}
												<div class="self-center">
													<svg
														class=" w-4 h-4"
														viewBox="0 0 24 24"
														fill="currentColor"
														xmlns="http://www.w3.org/2000/svg"
													>
														<style>
															.spinner_ajPY {
																transform-origin: center;
																animation: spinner_AtaB 0.75s infinite linear;
															}

															@keyframes spinner_AtaB {
																100% {
																	transform: rotate(360deg);
																}
															}
														</style>
														<path
															d="M12,1A11,11,0,1,0,23,12,11,11,0,0,0,12,1Zm0,19a8,8,0,1,1,8-8A8,8,0,0,1,12,20Z"
															opacity=".25"
														/>
														<path
															d="M10.14,1.16a11,11,0,0,0-9,8.92A1.59,1.59,0,0,0,2.46,12,1.52,1.52,0,0,0,4.11,10.7a8,8,0,0,1,6.66-6.61A1.42,1.42,0,0,0,12,2.69h0A1.57,1.57,0,0,0,10.14,1.16Z"
															class="spinner_ajPY"
														/>
													</svg>
												</div>
											{:else}
												<svg
													xmlns="http://www.w3.org/2000/svg"
													viewBox="0 0 16 16"
													fill="currentColor"
													class="w-4 h-4"
												>
													<path
														d="M8.75 2.75a.75.75 0 0 0-1.5 0v5.69L5.03 6.22a.75.75 0 0 0-1.06 1.06l3.5 3.5a.75.75 0 0 0 1.06 0l3.5-3.5a.75.75 0 0 0-1.06-1.06L8.75 8.44V2.75Z"
													/>
													<path
														d="M3.5 9.75a.75.75 0 0 0-1.5 0v1.5A2.75 2.75 0 0 0 4.75 14h6.5A2.75 2.75 0 0 0 14 11.25v-1.5a.75.75 0 0 0-1.5 0v1.5c0 .69-.56 1.25-1.25 1.25h-6.5c-.69 0-1.25-.56-1.25-1.25v-1.5Z"
													/>
												</svg>
											{/if}
										</button>
									</div>
								</div>
							</div>
						{/if}

						<div class="  mb-2.5 flex w-full justify-between">
							<div class=" self-center text-xs font-medium">{$i18n.t('Top K')}</div>
							<div class="flex items-center relative">
								<input
									class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
									type="number"
									placeholder={$i18n.t('Enter Top K')}
									bind:value={querySettings.k}
									autocomplete="off"
									min="0"
								/>
							</div>
						</div>

						{#if querySettings.hybrid === true}
							<div class="mb-2.5 flex w-full justify-between">
								<div class="self-center text-xs font-medium">{$i18n.t('Top K Reranker')}</div>
								<div class="flex items-center relative">
									<input
										class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
										type="number"
										placeholder={$i18n.t('Enter Top K Reranker')}
										bind:value={querySettings.k_reranker}
										autocomplete="off"
										min="0"
									/>
								</div>
							</div>
						{/if}

						{#if querySettings.hybrid === true}
							<div class="  mb-2.5 flex flex-col w-full justify-between">
								<div class=" flex w-full justify-between">
									<div class=" self-center text-xs font-medium">{$i18n.t('Minimum Score')}</div>
									<div class="flex items-center relative">
										<input
											class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
											type="number"
											step="0.01"
											placeholder={$i18n.t('Enter Score')}
											bind:value={querySettings.r}
											autocomplete="off"
											min="0.0"
											title={$i18n.t(
												'The score should be a value between 0.0 (0%) and 1.0 (100%).'
											)}
										/>
									</div>
								</div>
								<div class="mt-1 text-xs text-gray-400 dark:text-gray-500">
									{$i18n.t(
										'Note: If you set a minimum score, the search will only return documents with a score greater than or equal to the minimum score.'
									)}
								</div>
							</div>
						{/if}
					{/if}

					<div class="  mb-2.5 flex flex-col w-full justify-between">
						<div class=" mb-1 text-xs font-medium">{$i18n.t('RAG Template')}</div>
						<div class="flex w-full items-center relative">
							<Tooltip
								content={$i18n.t('Leave empty to use the default prompt, or enter a custom prompt')}
								placement="top-start"
								className="w-full"
							>
								<Textarea
									bind:value={querySettings.template}
									placeholder={$i18n.t(
										'Leave empty to use the default prompt, or enter a custom prompt'
									)}
								/>
							</Tooltip>
						</div>
					</div>
				</div>
			{/if}

			<div class="mb-3">
				<div class=" mb-2.5 text-base font-medium">{$i18n.t('Files')}</div>

				<hr class=" border-gray-100 dark:border-gray-850 my-2" />

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('Max Upload Size')}</div>
					<div class="flex items-center relative">
						<Tooltip
							content={$i18n.t(
								'The maximum file size in MB. If the file size exceeds this limit, the file will not be uploaded.'
							)}
							placement="top-start"
						>
							<input
								class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
								type="number"
								placeholder={$i18n.t('Leave empty for unlimited')}
								bind:value={fileMaxSize}
								autocomplete="off"
								min="0"
							/>
						</Tooltip>
					</div>
				</div>

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('Max Upload Count')}</div>
					<div class="flex items-center relative">
						<Tooltip
							content={$i18n.t(
								'The maximum number of files that can be used at once in chat. If the number of files exceeds this limit, the files will not be uploaded.'
							)}
							placement="top-start"
						>
							<input
								class="flex-1 w-full rounded-lg text-sm bg-transparent outline-hidden"
								type="number"
								placeholder={$i18n.t('Leave empty for unlimited')}
								bind:value={fileMaxCount}
								autocomplete="off"
								min="0"
							/>
						</Tooltip>
					</div>
				</div>
			</div>

			<div class="mb-3">
				<div class=" mb-2.5 text-base font-medium">{$i18n.t('Integration')}</div>

				<hr class=" border-gray-100 dark:border-gray-850 my-2" />

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('Google Drive')}</div>
					<div class="flex items-center relative">
						<Switch bind:state={enableGoogleDriveIntegration} />
					</div>
				</div>

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('OneDrive')}</div>
					<div class="flex items-center relative">
						<Switch bind:state={enableOneDriveIntegration} />
					</div>
				</div>
			</div>

			<div class="mb-3">
				<div class=" mb-2.5 text-base font-medium">{$i18n.t('Danger Zone')}</div>

				<hr class=" border-gray-100 dark:border-gray-850 my-2" />

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">{$i18n.t('Reset Upload Directory')}</div>
					<div class="flex items-center relative">
						<button
							class="text-xs"
							on:click={() => {
								showResetUploadDirConfirm = true;
							}}
						>
							{$i18n.t('Reset')}
						</button>
					</div>
				</div>

				<div class="  mb-2.5 flex w-full justify-between">
					<div class=" self-center text-xs font-medium">
						{$i18n.t('Reset Vector Storage/Knowledge')}
					</div>
					<div class="flex items-center relative">
						<button
							class="text-xs"
							on:click={() => {
								showResetConfirm = true;
							}}
						>
							{$i18n.t('Reset')}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>
	<div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>
	</div>
</form>
