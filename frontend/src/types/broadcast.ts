export interface BroadcastPreviewRequest {
  subject: string;
  body: string;
  order_id?: string;
}

export interface BroadcastPreviewResponse {
  subject: string;
  body_text: string;
  body_html: string;
  sample_order_number?: string | null;
  sample_exhibitor_name?: string | null;
  sample_recipient_email?: string | null;
  sample_spots?: string | null;
  total_eligible_recipients: number;
}

export interface BroadcastSendRequest {
  subject: string;
  body: string;
  target_audience?: 'all_confirmed' | 'selected';
  selected_order_ids?: string[];
  is_test?: boolean;
  test_recipient?: string;
}

export interface BroadcastSendResponse {
  status: string;
  event_id: string;
  event_title: string;
  total_targeted: number;
  recipients_without_email: number;
  is_test: boolean;
  test_recipient?: string | null;
  message: string;
}

export interface DynamicTagItem {
  tag: string;
  label: string;
  description: string;
  example: string;
}

export const AVAILABLE_DYNAMIC_TAGS: DynamicTagItem[] = [
  {
    tag: '{{exposant.prenom}}',
    label: 'Prénom',
    description: "Prénom de l'exposant",
    example: 'Monique',
  },
  {
    tag: '{{exposant.nom}}',
    label: 'Nom',
    description: "Nom de famille de l'exposant",
    example: 'Durand',
  },
  {
    tag: '{{commande.numero}}',
    label: 'N° Commande',
    description: 'Identifiant public de la commande',
    example: 'GVG-2026-ABCD',
  },
  {
    tag: '{{commande.emplacements}}',
    label: 'Emplacements',
    description: 'Numéros des stands réservés',
    example: 'A-12, A-13',
  },
  {
    tag: '{{evenement.titre}}',
    label: 'Titre Événement',
    description: "Nom officiel de l'événement",
    example: 'Grand Vide-Grenier',
  },
  {
    tag: '{{evenement.date}}',
    label: 'Date Événement',
    description: "Date complète de l'événement",
    example: '14 juin 2026',
  },
  {
    tag: '{{commande.lien}}',
    label: 'Lien Réservation',
    description: 'URL sécurisée sans mot de passe',
    example: 'https://.../confirmation/...',
  },
];

