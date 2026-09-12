import React, { useState, useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import {
  ArrowLeft,
  Layers,
  MapPin,
  Info,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Copy,
  Hash,
  Magnet,
  CheckSquare,
  Trash2,
  X,
} from 'lucide-react';
import { EventModel } from '../types/event';
import {
  SpotFeature,
  GeoJSONPolygon,
  SpotCreateInput,
  SpotBatchRenumberInput,
} from '../types/spot';
import {
  fetchSpots,
  createSpot,
  updateSpot,
  deleteSpot,
  createSpotsBatch,
  renumberSpotsBatch,
  getImageUrl,
} from '../lib/api';
import { SpotPropertyDrawer, SpotFormData } from './SpotPropertyDrawer';
import { DuplicateSpotModal } from './DuplicateSpotModal';
import { BatchRenumberModal } from './BatchRenumberModal';

interface SpotEditorProps {
  event: EventModel;
  onBack: () => void;
  onEventUpdated?: (updatedEvent: EventModel) => void;
  onNavigateToCalibration?: () => void;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function getNextProvisionalLabel(spots: SpotFeature[]): string {
  let maxNum = 0;
  for (const s of spots) {
    const match = s.properties.label.match(/(?:stand\s*|a|#)?(\d+)/i);
    if (match) {
      const n = parseInt(match[1], 10);
      if (n > maxNum) maxNum = n;
    }
  }
  return `Stand ${maxNum + 1}`;
}

export const SpotEditor: React.FC<SpotEditorProps> = ({
  event,
  onBack,
  onNavigateToCalibration,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const spotsLayerGroupRef = useRef<L.LayerGroup | null>(null);
  const pendingLayerRef = useRef<L.Polygon | null>(null);
  const spotLayersMapRef = useRef<Map<string, L.Layer>>(new Map());

  const [spots, setSpots] = useState<SpotFeature[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [mapReady, setMapReady] = useState<boolean>(false);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [isNewSpot, setIsNewSpot] = useState<boolean>(false);
  const [selectedSpot, setSelectedSpot] = useState<SpotFeature | null>(null);
  const [provisionalGeometry, setProvisionalGeometry] = useState<GeoJSONPolygon | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Multi-selection state
  const [selectedSpotIds, setSelectedSpotIds] = useState<string[]>([]);
  const [isMultiSelectMode, setIsMultiSelectMode] = useState<boolean>(false);
  const isMultiSelectModeRef = useRef<boolean>(false);
  isMultiSelectModeRef.current = isMultiSelectMode;

  // Duplication modal state
  const [isDuplicateModalOpen, setIsDuplicateModalOpen] = useState<boolean>(false);
  const [spotToDuplicate, setSpotToDuplicate] = useState<SpotFeature | null>(null);
  const [isDuplicating, setIsDuplicating] = useState<boolean>(false);

  // Batch renumbering modal state
  const [isBatchRenumberModalOpen, setIsBatchRenumberModalOpen] = useState<boolean>(false);
  const [isBatchRenumbering, setIsBatchRenumbering] = useState<boolean>(false);

  // Magnetic snapping state
  const [snapEnabled, setSnapEnabled] = useState<boolean>(true);
  const [snapDistance, setSnapDistance] = useState<number>(15);

  // Batch deleting state
  const [isBatchDeleting, setIsBatchDeleting] = useState<boolean>(false);

  // Tile layer state for outdoor mode
  const [tileLayerType, setTileLayerType] = useState<'osm' | 'satellite'>('osm');
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  // Load spots from backend
  const loadSpots = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSpots(event.id);
      setSpots(data.features || []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du chargement des emplacements');
    } finally {
      setLoading(false);
    }
  }, [event.id]);

  useEffect(() => {
    loadSpots();
  }, [loadSpots]);

  // Handle saving spot from drawer
  const handleSaveSpot = async (formData: SpotFormData) => {
    setIsSaving(true);
    try {
      if (isNewSpot) {
        if (!provisionalGeometry) {
          throw new Error('Géométrie du stand manquante.');
        }

        const newFeature = await createSpot(event.id, {
          label: formData.label,
          linear_meters: formData.linear_meters,
          price_cents: formData.price_cents,
          geometry: provisionalGeometry,
        });

        // Clean up pending Geoman layer from map
        if (pendingLayerRef.current && mapInstanceRef.current) {
          mapInstanceRef.current.removeLayer(pendingLayerRef.current);
          pendingLayerRef.current = null;
        }

        setSpots((prev) => [...prev, newFeature]);
        setDrawerOpen(false);
        setIsNewSpot(false);
        setSelectedSpot(null);
        setProvisionalGeometry(null);
        showToast(`Stand « ${newFeature.properties.label} » créé avec succès !`);
      } else if (selectedSpot) {
        const updatedFeature = await updateSpot(event.id, selectedSpot.id, {
          label: formData.label,
          linear_meters: formData.linear_meters,
          price_cents: formData.price_cents,
        });

        setSpots((prev) =>
          prev.map((s) => (s.id === updatedFeature.id ? updatedFeature : s))
        );
        setSelectedSpot(updatedFeature);
        setDrawerOpen(false);
        showToast(`Stand « ${updatedFeature.properties.label} » mis à jour !`);
      }
    } catch (err: unknown) {
      throw err;
    } finally {
      setIsSaving(false);
    }
  };

  // Handle deleting spot
  const handleDeleteSpot = async (spotId: string) => {
    setIsDeleting(true);
    try {
      await deleteSpot(event.id, spotId);

      // Remove layer from map
      const layer = spotLayersMapRef.current.get(spotId);
      if (layer && spotsLayerGroupRef.current) {
        spotsLayerGroupRef.current.removeLayer(layer);
        spotLayersMapRef.current.delete(spotId);
      }

      setSpots((prev) => prev.filter((s) => s.id !== spotId));
      setDrawerOpen(false);
      setSelectedSpot(null);
      showToast('Emplacement supprimé avec succès.');
    } catch (err: unknown) {
      throw err;
    } finally {
      setIsDeleting(false);
    }
  };

  // Close drawer and cancel pending layer
  const handleCloseDrawer = () => {
    if (pendingLayerRef.current && mapInstanceRef.current) {
      mapInstanceRef.current.removeLayer(pendingLayerRef.current);
      pendingLayerRef.current = null;
    }
    setDrawerOpen(false);
    setIsNewSpot(false);
    setSelectedSpot(null);
    setProvisionalGeometry(null);
  };

  // Open duplication dialog for a spot
  const handleOpenDuplicate = (spot: SpotFeature) => {
    setSpotToDuplicate(spot);
    setIsDuplicateModalOpen(true);
  };

  // Execute batch duplication
  const handleDuplicateSpots = async (newSpots: SpotCreateInput[]) => {
    setIsDuplicating(true);
    try {
      const res = await createSpotsBatch(event.id, { spots: newSpots });
      setSpots((prev) => [...prev, ...res.features]);
      setIsDuplicateModalOpen(false);
      setSpotToDuplicate(null);
      showToast(`${res.created_count || newSpots.length} stands créés avec succès !`);
    } catch (err: unknown) {
      throw err;
    } finally {
      setIsDuplicating(false);
    }
  };

  // Execute batch renumbering
  const handleRenumberSpots = async (input: SpotBatchRenumberInput) => {
    setIsBatchRenumbering(true);
    try {
      const res = await renumberSpotsBatch(event.id, input);
      const updatedMap = new Map(res.features.map((f) => [f.id, f]));
      setSpots((prev) => prev.map((s) => updatedMap.get(s.id) || s));
      setIsBatchRenumberModalOpen(false);
      setSelectedSpotIds([]);
      showToast(`${res.updated_count || res.features.length} stands renumérotés avec succès !`);
    } catch (err: unknown) {
      throw err;
    } finally {
      setIsBatchRenumbering(false);
    }
  };

  // Execute batch deletion of selected spots
  const handleBatchDelete = async () => {
    if (selectedSpotIds.length === 0) return;
    const count = selectedSpotIds.length;
    const confirmed = window.confirm(
      `Êtes-vous sûr de vouloir supprimer les ${count} stands sélectionnés ?`
    );
    if (!confirmed) return;

    setIsBatchDeleting(true);
    const deletedIds: string[] = [];
    try {
      for (const spotId of selectedSpotIds) {
        await deleteSpot(event.id, spotId);
        deletedIds.push(spotId);
        const layer = spotLayersMapRef.current.get(spotId);
        if (layer && spotsLayerGroupRef.current) {
          spotsLayerGroupRef.current.removeLayer(layer);
          spotLayersMapRef.current.delete(spotId);
        }
      }
      setSpots((prev) => prev.filter((s) => !deletedIds.includes(s.id)));
      setSelectedSpotIds([]);
      setSelectedSpot(null);
      setDrawerOpen(false);
      showToast(`${count} stands supprimés avec succès.`);
    } catch (err: unknown) {
      if (deletedIds.length > 0) {
        setSpots((prev) => prev.filter((s) => !deletedIds.includes(s.id)));
        setSelectedSpotIds((prev) => prev.filter((id) => !deletedIds.includes(id)));
      }
      showToast(
        err instanceof Error ? err.message : 'Erreur lors de la suppression groupée',
        'error'
      );
    } finally {
      setIsBatchDeleting(false);
    }
  };

  // Dynamic snapping update on Leaflet-Geoman instance
  useEffect(() => {
    if (mapInstanceRef.current && (mapInstanceRef.current as any).pm) {
      (mapInstanceRef.current as any).pm.setGlobalOptions({
        snappable: snapEnabled,
        snapDistance: snapDistance,
        snapSegment: true,
        snapVertex: true,
        snapMiddle: false,
      });
    }
  }, [snapEnabled, snapDistance]);

  // Initialize Leaflet and Leaflet-Geoman
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Planar mode without image yet
    if (event.map_type === 'planar' && !event.background_image_url) {
      return;
    }

    // Cleanup previous map instance if any
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    let isMounted = true;

    if (event.map_type === 'geographic') {
      // 1. Geographic mode setup
      const lat = event.center_latitude ?? 46.603354;
      const lng = event.center_longitude ?? 1.888334;
      const zoom = event.default_zoom ?? 16;

      const map = L.map(mapContainerRef.current, {
        center: [lat, lng],
        zoom: zoom,
        zoomControl: true,
      });

      const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
      const satUrl =
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      const satAttr =
        'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP';

      const initialUrl = tileLayerType === 'satellite' ? satUrl : osmUrl;
      const initialAttr = tileLayerType === 'satellite' ? satAttr : osmAttr;

      const tileLayer = L.tileLayer(initialUrl, {
        maxZoom: 19,
        attribution: initialAttr,
      }).addTo(map);
      tileLayerRef.current = tileLayer;

      setupGeoman(map);

      const spotsGroup = L.layerGroup().addTo(map);
      spotsLayerGroupRef.current = spotsGroup;
      mapInstanceRef.current = map;
      setMapReady(true);

      setTimeout(() => {
        if (isMounted && mapInstanceRef.current) {
          mapInstanceRef.current.invalidateSize();
        }
      }, 100);
    } else {
      // 2. Planar mode setup (L.CRS.Simple)
      const imageUrl = getImageUrl(event.background_image_url);
      const img = new Image();
      img.src = imageUrl;

      img.onerror = () => {
        if (!isMounted) return;
        setError("Impossible de charger l'image du fond de plan de salle (introuvable ou erreur réseau).");
        setLoading(false);
      };

      img.onload = () => {
        if (!isMounted || !mapContainerRef.current) return;

        const w = img.naturalWidth;
        const h = img.naturalHeight;

        const map = L.map(mapContainerRef.current, {
          crs: L.CRS.Simple,
          minZoom: -2,
          maxZoom: 3,
          zoomSnap: 0.25,
          zoomDelta: 0.5,
        });

        const bounds = new L.LatLngBounds([0, 0], [h, w]);
        L.imageOverlay(imageUrl, bounds).addTo(map);

        map.fitBounds(bounds);
        map.setMaxBounds(bounds.pad(0.2));

        setupGeoman(map);

        const spotsGroup = L.layerGroup().addTo(map);
        spotsLayerGroupRef.current = spotsGroup;
        mapInstanceRef.current = map;
        setMapReady(true);

        setTimeout(() => {
          if (isMounted && mapInstanceRef.current) {
            mapInstanceRef.current.invalidateSize();
          }
        }, 100);
      };
    }

    function setupGeoman(map: L.Map) {
      // Set Geoman language to French if available
      try {
        if (map.pm && typeof map.pm.setLang === 'function') {
          map.pm.setLang('fr');
        }
      } catch {
        // ignore
      }

      // Configure global magnetic snapping
      map.pm.setGlobalOptions({
        snappable: snapEnabled,
        snapDistance: snapDistance,
        snapSegment: true,
        snapVertex: true,
        snapMiddle: false,
      });

      // Initialize Geoman drawing and editing toolbar controls (explicitly disable cutPolygon and drawText)
      map.pm.addControls({
        position: 'topleft',
        drawCircle: false,
        drawCircleMarker: false,
        drawMarker: false,
        drawPolyline: false,
        drawPolygon: false,
        drawRectangle: true,
        drawText: false,
        cutPolygon: false,
        editMode: true,
        dragMode: true,
        rotateMode: true,
        removalMode: true,
        snappingButton: true,
      });

      // Map background click: deselect if clicking empty space
      map.on('click', () => {
        if (
          map.pm &&
          (map.pm.globalDrawModeEnabled() || map.pm.globalRemovalModeEnabled())
        ) {
          return;
        }
        setSelectedSpotIds([]);
        setSelectedSpot(null);
        setDrawerOpen(false);
      });

      // Event: Cleanup any pending layer when a new drawing starts
      map.on('pm:drawstart', () => {
        if (pendingLayerRef.current) {
          map.removeLayer(pendingLayerRef.current);
          pendingLayerRef.current = null;
        }
      });

      // Event: Finished drawing a new shape
      map.on('pm:create', (e: { layer: L.Layer }) => {
        if (pendingLayerRef.current) {
          map.removeLayer(pendingLayerRef.current);
          pendingLayerRef.current = null;
        }

        const layer = e.layer as L.Polygon;
        pendingLayerRef.current = layer;

        const geojson = layer.toGeoJSON();
        const polyGeom = geojson.geometry as GeoJSONPolygon;

        setProvisionalGeometry(polyGeom);
        setIsNewSpot(true);
        setSelectedSpot(null);
        setDrawerOpen(true);
      });

      // Event: Layer removed via Geoman removal tool
      map.on('pm:remove', async (e: { layer: L.Layer }) => {
        const removedLayer = e.layer;
        let targetSpotId: string | null = null;
        for (const [sId, l] of spotLayersMapRef.current.entries()) {
          if (l === removedLayer) {
            targetSpotId = sId;
            break;
          }
        }

        if (targetSpotId) {
          const confirmed = window.confirm(
            'Êtes-vous sûr de vouloir supprimer cet emplacement ?'
          );
          if (confirmed) {
            try {
              await deleteSpot(event.id, targetSpotId);
              spotLayersMapRef.current.delete(targetSpotId);
              setSpots((prev) => prev.filter((s) => s.id !== targetSpotId));
              if (selectedSpot && selectedSpot.id === targetSpotId) {
                setDrawerOpen(false);
                setSelectedSpot(null);
              }
              showToast('Emplacement supprimé');
            } catch (err: unknown) {
              showToast(
                err instanceof Error ? err.message : 'Erreur lors de la suppression',
                'error'
              );
              // Re-add layer if deletion failed
              if (spotsLayerGroupRef.current) {
                spotsLayerGroupRef.current.addLayer(removedLayer);
              }
            }
          } else {
            // User cancelled removal, re-add layer to map
            if (spotsLayerGroupRef.current) {
              spotsLayerGroupRef.current.addLayer(removedLayer);
            }
          }
        }
      });
    }

    return () => {
      isMounted = false;
      setMapReady(false);
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
      spotLayersMapRef.current.clear();
      spotsLayerGroupRef.current = null;
    };
  }, [event]);

  // Sync and render spots onto Leaflet layer group whenever spots state changes or map is ready
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = spotsLayerGroupRef.current;
    if (!map || !group) return;

    // Clear existing layers from group
    group.clearLayers();
    spotLayersMapRef.current.clear();

    const statusColors = {
      available: { stroke: '#047857', fill: '#10b981' },
      reserved: { stroke: '#1d4ed8', fill: '#3b82f6' },
      locked: { stroke: '#b45309', fill: '#f59e0b' },
      blocked: { stroke: '#374151', fill: '#6b7280' },
    };

    spots.forEach((spot) => {
      const colors = statusColors[spot.properties.status] || statusColors.available;
      const isSelected = selectedSpotIds.includes(spot.id) || selectedSpot?.id === spot.id;

      // Create GeoJSON layer with active highlight if selected
      const geoLayer = L.geoJSON(spot, {
        style: {
          color: isSelected ? '#4f46e5' : colors.stroke,
          fillColor: isSelected ? '#6366f1' : colors.fill,
          weight: isSelected ? 4 : 2,
          opacity: isSelected ? 1 : 0.9,
          fillOpacity: isSelected ? 0.7 : 0.45,
          dashArray: isSelected ? '4, 4' : undefined,
        },
      });

      // Extract the single polygon layer inside the GeoJSON group
      geoLayer.eachLayer((layer) => {
        const poly = layer as L.Polygon;
        let prevLatLngs = poly.getLatLngs();

        // Safe HTML escaping for tooltip label
        const escapedLabel = escapeHtml(spot.properties.label);
        poly.bindTooltip(
          `<div class="text-center font-bold leading-tight select-none">
            <div class="text-xs text-gray-900">${escapedLabel}</div>
            <div class="text-[10px] text-gray-600 font-medium">${spot.properties.linear_meters}m • ${spot.properties.price.toFixed(2)}€</div>
          </div>`,
          {
            permanent: true,
            direction: 'center',
            className: 'spot-label-tooltip',
          }
        );

        // Click on spot to inspect / edit in drawer or toggle in multi-selection
        poly.on('click', (e: L.LeafletMouseEvent) => {
          if (
            map.pm &&
            (map.pm.globalDrawModeEnabled() || map.pm.globalRemovalModeEnabled())
          ) {
            return;
          }
          L.DomEvent.stopPropagation(e);

          if (isMultiSelectModeRef.current || e.originalEvent?.shiftKey) {
            setSelectedSpotIds((prev) => {
              const exists = prev.includes(spot.id);
              const next = exists ? prev.filter((id) => id !== spot.id) : [...prev, spot.id];
              if (next.length === 1) {
                const single = spots.find((s) => s.id === next[0]) || spot;
                setSelectedSpot(single);
              } else {
                setSelectedSpot(null);
                setDrawerOpen(false);
              }
              return next;
            });
          } else {
            setSelectedSpotIds([spot.id]);
            setSelectedSpot(spot);
            setIsNewSpot(false);
            setDrawerOpen(true);
          }
        });

        // Save position before modification starts so we can revert on failure
        poly.on('pm:dragstart', () => {
          prevLatLngs = poly.getLatLngs();
        });
        poly.on('pm:rotatestart', () => {
          prevLatLngs = poly.getLatLngs();
        });

        // Listen for rotate, drag, and edit completions to persist updated geometry
        const persistGeometryUpdate = async () => {
          const updatedGeoJSON = poly.toGeoJSON();
          const newGeom = updatedGeoJSON.geometry as GeoJSONPolygon;

          try {
            const updated = await updateSpot(event.id, spot.id, {
              geometry: newGeom,
            });
            setSpots((prev) =>
              prev.map((s) => (s.id === updated.id ? updated : s))
            );
            prevLatLngs = poly.getLatLngs();
            showToast(`Géométrie de « ${spot.properties.label} » mise à jour.`);
          } catch (err: unknown) {
            // Revert coordinates on failure
            if (prevLatLngs) {
              poly.setLatLngs(prevLatLngs);
            }
            showToast(
              err instanceof Error ? err.message : 'Erreur lors de la mise à jour de la position',
              'error'
            );
          }
        };

        poly.on('pm:rotateend', persistGeometryUpdate);
        poly.on('pm:dragend', persistGeometryUpdate);
        poly.on('pm:edit', persistGeometryUpdate);

        group.addLayer(poly);
        spotLayersMapRef.current.set(spot.id, poly);
      });
    });
  }, [spots, event.id, mapReady, selectedSpot?.id, selectedSpotIds]);

  // Switch outdoor tile layer between OSM and Satellite dynamically
  const toggleTileLayer = (type: 'osm' | 'satellite') => {
    setTileLayerType(type);
    if (!mapInstanceRef.current || event.map_type !== 'geographic') return;

    if (tileLayerRef.current) {
      mapInstanceRef.current.removeLayer(tileLayerRef.current);
    }

    const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    const satUrl =
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
    const satAttr =
      'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP';

    const url = type === 'satellite' ? satUrl : osmUrl;
    const attr = type === 'satellite' ? satAttr : osmAttr;

    tileLayerRef.current = L.tileLayer(url, {
      maxZoom: 19,
      attribution: attr,
    }).addTo(mapInstanceRef.current);
  };

  // Stats without floating point drift
  const totalLinearMeters = spots.reduce((sum, s) => sum + s.properties.linear_meters, 0);
  const totalRevenueCents = spots.reduce((sum, s) => sum + s.properties.price_cents, 0);
  const totalRevenueEuros = totalRevenueCents / 100;
  const nextLabel = getNextProvisionalLabel(spots);

  // Missing floorplan view in planar mode
  if (event.map_type === 'planar' && !event.background_image_url) {
    return (
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-12 text-center max-w-xl mx-auto my-8">
        <div className="w-16 h-16 bg-amber-50 text-amber-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Layers className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-gray-900">Fond de plan de salle requis</h3>
        <p className="text-sm text-gray-500 mt-2">
          Cet événement est configuré en mode « Plan de Salle / Intérieur », mais aucune image
          schématique (PNG, JPEG) n'a encore été téléversée. Vous devez calibrer le plan avant de
          pouvoir dessiner les stands.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 hover:bg-gray-100 rounded-lg text-sm font-semibold transition"
          >
            Retour
          </button>
          {onNavigateToCalibration && (
            <button
              type="button"
              onClick={onNavigateToCalibration}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-semibold shadow-sm transition flex items-center gap-2"
            >
              <MapPin className="w-4 h-4" />
              <span>Calibrer le plan de salle</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Bar Header */}
      <div className="bg-white border border-gray-200 rounded-2xl p-4 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition"
            title="Retour à la liste"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-gray-900">{event.title}</h2>
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                Éditeur de Stands
              </span>
              <span className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                {event.map_type === 'geographic' ? 'Extérieur (GPS)' : 'Intérieur (Salle)'}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              Tarif de base :{' '}
              <span className="font-bold text-gray-700">
                {(event.price_per_meter ?? event.price_per_meter_cents / 100).toFixed(2)} €/m
              </span>
            </p>
          </div>
        </div>

        {/* Global Summary Stats */}
        <div className="flex items-center gap-3 self-end md:self-auto">
          <div className="bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-xl text-center">
            <div className="text-xs text-gray-500 font-medium">Stands</div>
            <div className="text-base font-black text-gray-900">{spots.length}</div>
          </div>
          <div className="bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-xl text-center">
            <div className="text-xs text-gray-500 font-medium">Mètres totaux</div>
            <div className="text-base font-black text-emerald-700">{totalLinearMeters.toFixed(1)} m</div>
          </div>
          <div className="bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-xl text-center">
            <div className="text-xs text-gray-500 font-medium">Potentiel</div>
            <div className="text-base font-black text-emerald-700">
              {totalRevenueEuros.toFixed(2)} €
            </div>
          </div>

          {/* Satellite switch for outdoor mode */}
          {event.map_type === 'geographic' && (
            <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
              <button
                type="button"
                onClick={() => toggleTileLayer('osm')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition ${
                  tileLayerType === 'osm'
                    ? 'bg-white text-gray-900 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                Plan OSM
              </button>
              <button
                type="button"
                onClick={() => toggleTileLayer('satellite')}
                className={`px-2.5 py-1 text-xs font-semibold rounded-md transition ${
                  tileLayerType === 'satellite'
                    ? 'bg-white text-gray-900 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                Satellite
              </button>
            </div>
          )}

          {/* Magnetic snapping control */}
          <div className="flex items-center gap-1 bg-gray-50 border border-gray-200 rounded-xl p-1">
            <button
              type="button"
              onClick={() => setSnapEnabled(!snapEnabled)}
              className={`px-2.5 py-1 text-xs font-bold rounded-lg transition flex items-center gap-1.5 ${
                snapEnabled
                  ? 'bg-emerald-600 text-white shadow-xs'
                  : 'text-gray-500 hover:text-gray-900'
              }`}
              title={snapEnabled ? 'Magnétisme activé' : 'Magnétisme désactivé'}
            >
              <Magnet className="w-3.5 h-3.5" />
              <span>{snapEnabled ? `Snap ${snapDistance}px` : 'Snap off'}</span>
            </button>
            {snapEnabled && (
              <button
                type="button"
                onClick={() => {
                  const nextDist =
                    snapDistance === 10
                      ? 15
                      : snapDistance === 15
                      ? 20
                      : snapDistance === 20
                      ? 30
                      : 10;
                  setSnapDistance(nextDist);
                }}
                className="px-2 py-1 text-xs font-bold text-gray-600 hover:text-gray-900 rounded transition bg-white border border-gray-200"
                title="Ajuster le seuil d'aimantation (pixels)"
              >
                {snapDistance}px
              </button>
            )}
          </div>

          {/* Multi-selection toggle */}
          <button
            type="button"
            onClick={() => {
              const nextMode = !isMultiSelectMode;
              setIsMultiSelectMode(nextMode);
              if (!nextMode) {
                setSelectedSpotIds([]);
              }
            }}
            className={`px-3 py-1.5 text-xs font-bold rounded-xl border transition flex items-center gap-1.5 ${
              isMultiSelectMode
                ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                : 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100'
            }`}
            title="Activer la sélection multiple de stands"
          >
            <CheckSquare className="w-3.5 h-3.5" />
            <span>Sélection multiple {isMultiSelectMode ? 'ON' : ''}</span>
          </button>

          {/* Quick duplicate button if single spot selected */}
          {selectedSpot && (
            <button
              type="button"
              onClick={() => handleOpenDuplicate(selectedSpot)}
              className="px-3 py-1.5 text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 hover:bg-emerald-100 rounded-xl transition flex items-center gap-1.5 shadow-xs"
              title="Dupliquer le stand sélectionné"
            >
              <Copy className="w-3.5 h-3.5 text-emerald-600" />
              <span>Dupliquer × N</span>
            </button>
          )}

          <button
            type="button"
            onClick={loadSpots}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition"
            title="Actualiser les emplacements"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Error alert banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-center justify-between text-xs font-semibold">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={loadSpots}
            className="text-red-700 hover:underline"
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Helper Banner */}
      <div className="bg-emerald-50/60 border border-emerald-200/80 rounded-xl px-4 py-2.5 text-xs text-emerald-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>
            <b>Mode d'emploi :</b> Utilisez l'outil <b>Rectangle</b> pour dessiner un stand. Cliquez sur un stand pour le modifier ou le <b>Dupliquer (× N)</b>. Maintenez <b>Shift</b> ou activez <b>Sélection multiple</b> pour renuméroter ou supprimer des allées entières. Le magnétisme aligne automatiquement vos stands bord à bord.
          </span>
        </div>
      </div>

      {/* Toast alert */}
      {toast && (
        <div
          className={`px-4 py-3 rounded-xl border flex items-center gap-2.5 text-xs font-semibold shadow-md animate-fade-in ${
            toast.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
              : 'bg-red-50 border-red-200 text-red-900'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0" />
          )}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Map Container */}
      <div className="relative w-full rounded-2xl overflow-hidden border border-gray-200 shadow-sm bg-gray-100 h-[720px]">
        <div ref={mapContainerRef} className="w-full h-full z-10" />

        {/* Floating Multi-Selection Action Bar */}
        {selectedSpotIds.length > 0 && (
          <div className="absolute bottom-6 left-1/2 z-30 bg-white/95 backdrop-blur-md border border-gray-200 shadow-xl rounded-2xl px-5 py-3 flex items-center gap-4 animate-slide-up-center">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-600 animate-pulse" />
              <span className="text-xs font-black text-gray-900">
                {selectedSpotIds.length}{' '}
                {selectedSpotIds.length === 1 ? 'stand sélectionné' : 'stands sélectionnés'}
              </span>
            </div>

            <div className="h-4 w-px bg-gray-200" />

            <div className="flex items-center gap-2">
              {selectedSpotIds.length === 1 && (
                <button
                  type="button"
                  onClick={() => {
                    const sp = spots.find((s) => s.id === selectedSpotIds[0]);
                    if (sp) handleOpenDuplicate(sp);
                  }}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                >
                  <Copy className="w-3.5 h-3.5" />
                  <span>Dupliquer × N</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => setIsBatchRenumberModalOpen(true)}
                className="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
              >
                <Hash className="w-3.5 h-3.5" />
                <span>Renuméroter ({selectedSpotIds.length})</span>
              </button>

              <button
                type="button"
                onClick={handleBatchDelete}
                disabled={isBatchDeleting}
                className="px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Supprimer ({selectedSpotIds.length})</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSelectedSpotIds([]);
                  setSelectedSpot(null);
                }}
                className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition"
                title="Désélectionner tout"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Floating Property Drawer */}
        <SpotPropertyDrawer
          isOpen={drawerOpen}
          isNew={isNewSpot}
          spot={selectedSpot}
          defaultLabel={nextLabel}
          eventPricePerMeterCents={event.price_per_meter_cents}
          onClose={handleCloseDrawer}
          onSave={handleSaveSpot}
          onDelete={handleDeleteSpot}
          onOpenDuplicateModal={handleOpenDuplicate}
          isSaving={isSaving}
          isDeleting={isDeleting}
        />
      </div>

      {/* Duplicate Spot Modal */}
      <DuplicateSpotModal
        isOpen={isDuplicateModalOpen}
        sourceSpot={spotToDuplicate}
        eventPricePerMeterCents={event.price_per_meter_cents}
        onClose={() => {
          setIsDuplicateModalOpen(false);
          setSpotToDuplicate(null);
        }}
        onDuplicate={handleDuplicateSpots}
        isDuplicating={isDuplicating}
      />

      {/* Batch Renumber Modal */}
      <BatchRenumberModal
        isOpen={isBatchRenumberModalOpen}
        selectedSpots={selectedSpotIds
          .map((id) => spots.find((s) => s.id === id))
          .filter((s): s is SpotFeature => s !== undefined)}
        onClose={() => setIsBatchRenumberModalOpen(false)}
        onRenumber={handleRenumberSpots}
        isRenumbering={isBatchRenumbering}
      />

      {/* Custom Styles for spot labels on Leaflet canvas */}
      <style>{`
        .spot-label-tooltip {
          background-color: rgba(255, 255, 255, 0.92) !important;
          border: 1px solid rgba(0, 0, 0, 0.15) !important;
          border-radius: 6px !important;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12) !important;
          padding: 2px 6px !important;
          pointer-events: none !important;
        }
        .spot-label-tooltip::before {
          display: none !important;
        }
        @keyframes slideInUp {
          from {
            transform: translate(-50%, 20px);
            opacity: 0;
          }
          to {
            transform: translate(-50%, 0);
            opacity: 1;
          }
        }
        .animate-slide-up-center {
          animation: slideInUp 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
      `}</style>
    </div>
  );
};
