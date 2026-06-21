import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface VolumeMetadata {
  volume_id: string;
  verification_id: string;
  volume_type: 'ct' | 'gt_mask' | 'dl_mask';
  volume_index: number;
  dimensions: [number, number, number];
  spacing: [number, number, number];
  origin?: [number, number, number];
  direction?: number[];
  hu_range: [number, number];
  num_slices: {
    axial: number;
    sagittal: number;
    coronal: number;
  };
  storage_prefix?: string;
}

export interface VisualizationMetadata {
  verification_id: string;
  status: 'ready' | 'processing' | 'not_processed' | 'simulated' | 'no_volumes';
  num_volumes: number;
  volumes: Array<{
    index: number;
    ct: VolumeMetadata | null;
    gt_mask: VolumeMetadata | null;
    dl_mask: VolumeMetadata | null;
    thumbnail: string | null;
  }>;
  storage_prefix: string;
  created_at: string;
}

export interface TileInfo {
  name: string;
  size: number;
  url: string;
}

export interface TilesResponse {
  verification_id: string;
  volume_index: number;
  volume_type: string;
  num_tiles: number;
  tiles: TileInfo[];
}

export interface HUPreset {
  center: number;
  width: number;
}

export interface HUPresetsResponse {
  presets: Record<string, HUPreset>;
  default: string;
  description: string;
}

export interface ProcessResponse {
  verification_id: string;
  status: string;
  message: string;
  num_volumes: number;
  visualization_url: string | null;
}

export async function getVisualizationVolumes(
  verificationId: string
): Promise<VisualizationMetadata> {
  const response = await axios.get<VisualizationMetadata>(
    `${API_BASE}/api/visualization/volumes/${verificationId}`
  );
  return response.data;
}

export async function getVolumeMetadata(
  verificationId: string,
  volumeIndex: number,
  volumeType: 'ct' | 'gt_mask' | 'dl_mask' = 'ct'
): Promise<VolumeMetadata> {
  const response = await axios.get<VolumeMetadata>(
    `${API_BASE}/api/visualization/volume/${verificationId}/${volumeIndex}/metadata`,
    { params: { volume_type: volumeType } }
  );
  return response.data;
}

export async function getSliceUrl(
  verificationId: string,
  volumeIndex: number,
  axis: 'axial' | 'sagittal' | 'coronal',
  sliceIndex: number,
  options: {
    volumeType?: 'ct' | 'gt_mask' | 'dl_mask';
    window?: string;
    overlay?: boolean;
    overlayType?: 'gt_mask' | 'dl_mask';
    overlayOpacity?: number;
  } = {}
): Promise<string> {
  const {
    volumeType = 'ct',
    window = 'lung',
    overlay = false,
    overlayType = 'dl_mask',
    overlayOpacity = 0.5,
  } = options;

  const response = await axios.get(
    `${API_BASE}/api/visualization/volume/${verificationId}/${volumeIndex}/slice/${axis}/${sliceIndex}`,
    {
      params: {
        volume_type: volumeType,
        window,
        overlay,
        overlay_type: overlayType,
        overlay_opacity: overlayOpacity,
      },
      responseType: 'blob',
    }
  );

  return URL.createObjectURL(response.data);
}

export async function getThumbnailUrl(
  verificationId: string,
  volumeIndex: number
): Promise<string> {
  const response = await axios.get(
    `${API_BASE}/api/visualization/volume/${verificationId}/${volumeIndex}/thumbnail`,
    { responseType: 'blob' }
  );
  return URL.createObjectURL(response.data);
}

export async function listVolumeTiles(
  verificationId: string,
  volumeIndex: number,
  volumeType: 'ct' | 'gt_mask' | 'dl_mask' = 'ct'
): Promise<TilesResponse> {
  const response = await axios.get<TilesResponse>(
    `${API_BASE}/api/visualization/volume/${verificationId}/${volumeIndex}/tiles`,
    { params: { volume_type: volumeType } }
  );
  return response.data;
}

export async function fetchTile(
  verificationId: string,
  volumeIndex: number,
  tileName: string,
  volumeType: 'ct' | 'gt_mask' | 'dl_mask' = 'ct'
): Promise<Uint8Array> {
  const response = await axios.get(
    `${API_BASE}/api/visualization/volume/${verificationId}/${volumeIndex}/tile/${tileName}`,
    {
      params: { volume_type: volumeType },
      responseType: 'arraybuffer',
    }
  );

  const pako = await import('pako');
  const decompressed = pako.inflate(new Uint8Array(response.data));
  return decompressed;
}

export async function getHUPresets(): Promise<HUPresetsResponse> {
  const response = await axios.get<HUPresetsResponse>(
    `${API_BASE}/api/visualization/presets/window`
  );
  return response.data;
}

export async function processVisualization(
  verificationId: string,
  options: {
    forceRegenerate?: boolean;
    useSimulated?: boolean;
  } = {}
): Promise<ProcessResponse> {
  const response = await axios.post<ProcessResponse>(
    `${API_BASE}/api/visualization/process/${verificationId}`,
    {
      force_regenerate: options.forceRegenerate || false,
      use_simulated: options.useSimulated || false,
    }
  );
  return response.data;
}

export async function exportScreenshot(
  verificationId: string,
  imageData: string,
  viewportInfo?: Record<string, unknown>
): Promise<{ success: boolean; screenshot_url?: string; error?: string }> {
  const response = await axios.post(
    `${API_BASE}/api/visualization/export/screenshot`,
    {
      verification_id: verificationId,
      image_data: imageData,
      viewport_info: viewportInfo,
    }
  );
  return response.data;
}

export function revokeSliceUrl(url: string): void {
  if (url.startsWith('blob:')) {
    URL.revokeObjectURL(url);
  }
}
