import React from 'react';
import {
  Mail,
  Send,
  Calendar,
  ShieldCheck,
  CheckCircle2,
  History,
} from 'lucide-react';
import { EventModel } from '../../types/event';
import { RemindersCard } from '../../components/RemindersCard';

interface CommunicationsTabProps {
  event: EventModel;
  onOpenBroadcast: () => void;
  confirmedCount: number;
}

export const CommunicationsTab: React.FC<CommunicationsTabProps> = ({
  event,
  onOpenBroadcast,
  confirmedCount,
}) => {
  const isCancelled = event.status === 'archived' || (event as any).status === 'cancelled';

  return (
    <div className="space-y-6">
      {/* Broadcast Announcement Banner */}
      <div className="bg-gradient-to-r from-emerald-600 to-teal-700 rounded-2xl p-6 text-white shadow-md flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 text-xs font-bold backdrop-blur-sm">
            <Mail className="w-3.5 h-3.5" />
            <span>Diffusion de Masse Personnalisée</span>
          </div>
          <h3 className="text-xl font-black tracking-tight">
            Envoyez un e-mail d'information à vos exposants
          </h3>
          <p className="text-sm text-emerald-50 leading-relaxed">
            Communiquez les consignes d'accès, la météo, le plan des allées ou des alertes de
            dernière minute. Vos messages sont automatiquement personnalisés avec les variables
            dynamiques (nom de l'exposant, numéros de stands, horaires d'installation).
          </p>
        </div>

        <div className="shrink-0 flex flex-col sm:flex-row items-center gap-3">
          <button
            type="button"
            onClick={onOpenBroadcast}
            disabled={confirmedCount === 0 || isCancelled}
            className="w-full sm:w-auto px-5 py-3 bg-white hover:bg-emerald-50 text-emerald-800 font-extrabold text-sm rounded-xl shadow-md transition flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4 text-emerald-600" />
            <span>Rédiger un E-mail ({confirmedCount} inscrits)</span>
          </button>
        </div>
      </div>

      {/* Scheduled Reminders (J-7 and J-2) */}
      <RemindersCard eventIdOrSlug={event.slug || event.id} />

      {/* Communications Guidelines & Legal Context */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4">
        <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Rappels Automatiques & Obligations Réglementaires</span>
        </h4>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-gray-600">
          <div className="p-4 bg-gray-50 rounded-xl border border-gray-200/70 space-y-1.5">
            <div className="font-bold text-gray-900 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>E-mails Transactionnels Instantanés</span>
            </div>
            <p>
              Dès la confirmation de leur réservation ou l'arbitrage d'un remboursement, les
              exposants reçoivent un récapitulatif détaillé avec leur numéro de stand et le lien
              sécurisé d'accès à leur attestation d'inscription.
            </p>
          </div>

          <div className="p-4 bg-gray-50 rounded-xl border border-gray-200/70 space-y-1.5">
            <div className="font-bold text-gray-900 flex items-center gap-1.5">
              <Calendar className="w-4 h-4 text-indigo-600" />
              <span>Pointage du Registre des Brocantes</span>
            </div>
            <p>
              Les relances automatiques à J-7 et J-2 rappellent aux exposants l'obligation de
              présenter leur pièce d'identité originale et leur attestation signée le matin de
              l'événement conformément à l'article L310-2 du Code de commerce.
            </p>
          </div>
        </div>
      </div>

      {/* Email Audit Log & Deliverability Assurance */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-3">
        <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
          <History className="w-4 h-4 text-emerald-600" />
          <span>Traçabilité & Journal des Envois d'E-mails</span>
        </h4>
        <p className="text-xs text-gray-500 leading-relaxed">
          Toutes les communications transactionnelles (confirmation, validation, remboursement) et de diffusion de masse sont consignées dans le journal d'audit SMTP avec horodatage certifié, statut de délivrabilité et protection anti-doublon.
        </p>
        <div className="flex flex-wrap items-center gap-2 pt-1 text-xs font-semibold text-gray-600">
          <span className="px-2.5 py-1 bg-gray-50 rounded-lg border border-gray-200">
            • Protection 0 doublon active
          </span>
          <span className="px-2.5 py-1 bg-gray-50 rounded-lg border border-gray-200">
            • Relances automatiques J-7 & J-2
          </span>
          <span className="px-2.5 py-1 bg-gray-50 rounded-lg border border-gray-200">
            • Envoi asynchrone sécurisé
          </span>
        </div>
      </div>
    </div>
  );
};
