import { EventCreateInput, EventUpdateInput, EventListResponse, EventModel } from '../types/event';
import {
  SpotCreateInput,
  SpotUpdateInput,
  SpotFeature,
  SpotFeatureCollection,
  SpotBatchCreateInput,
  SpotBatchCreateResponse,
  SpotBatchRenumberInput,
  SpotBatchRenumberResponse,
} from '../types/spot';

const API_BASE = import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api/v1` : '/api/v1';

export class ApiError extends Error {
  constructor(public status: number, public detail: string | Record<string, unknown>[]) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.name = 'ApiError';
  }
}

export async function createEvent(data: EventCreateInput): Promise<EventModel> {
  const response = await fetch(`${API_BASE}/events`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la création de l’événement';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function updateEvent(idOrSlug: string, data: EventUpdateInput): Promise<EventModel> {
  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(idOrSlug)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la mise à jour de l’événement';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function uploadBackgroundImage(eventIdOrSlug: string, file: File): Promise<EventModel> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/background-image`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    let detail = 'Erreur lors du téléversement du fond de plan';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchEvents(): Promise<EventListResponse> {
  const response = await fetch(`${API_BASE}/events`);
  if (!response.ok) {
    throw new Error('Erreur lors de la récupération des événements');
  }
  return response.json();
}

export async function fetchEvent(idOrSlug: string): Promise<EventModel> {
  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(idOrSlug)}`);
  if (!response.ok) {
    throw new Error('Événement introuvable');
  }
  return response.json();
}

export function getImageUrl(path?: string | null): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const baseUrl = import.meta.env.VITE_API_URL || '';
  return `${baseUrl}${path}`;
}

export async function fetchSpots(eventIdOrSlug: string): Promise<SpotFeatureCollection> {
  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots`);
  if (!response.ok) {
    let detail = 'Erreur lors de la récupération des emplacements';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function createSpot(eventIdOrSlug: string, data: SpotCreateInput): Promise<SpotFeature> {
  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la création du stand';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function updateSpot(
  eventIdOrSlug: string,
  spotId: string,
  data: SpotUpdateInput
): Promise<SpotFeature> {
  const response = await fetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/${encodeURIComponent(spotId)}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la mise à jour du stand';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function deleteSpot(eventIdOrSlug: string, spotId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/${encodeURIComponent(spotId)}`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la suppression du stand';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
}

export async function createSpotsBatch(
  eventIdOrSlug: string,
  data: SpotBatchCreateInput
): Promise<SpotBatchCreateResponse> {
  const response = await fetch(`${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    let detail = 'Erreur lors de la création groupée des stands';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function renumberSpotsBatch(
  eventIdOrSlug: string,
  data: SpotBatchRenumberInput
): Promise<SpotBatchRenumberResponse> {
  const response = await fetch(
    `${API_BASE}/events/${encodeURIComponent(eventIdOrSlug)}/spots/batch-renumber`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    let detail = 'Erreur lors de la renumérotation des stands';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function fetchPublicEvent(slug: string): Promise<import('../types/public').PublicEventResponse> {
  const response = await fetch(`${API_BASE}/public/events/${encodeURIComponent(slug)}`);
  if (!response.ok) {
    let detail = 'Événement introuvable';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}

export async function fetchPublicSpots(slug: string): Promise<import('../types/public').PublicSpotFeatureCollection> {
  const response = await fetch(`${API_BASE}/public/events/${encodeURIComponent(slug)}/spots`);
  if (!response.ok) {
    let detail = 'Erreur lors de la récupération des emplacements';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }
  return response.json();
}


