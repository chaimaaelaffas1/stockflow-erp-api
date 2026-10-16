# ➕ StockFlow — Ajouts hors plan

> Journal des éléments ajoutés **qui n'étaient pas prévus** dans le plan initial du projet.
> À compléter au fur et à mesure.

---

## 📋 Tableau récapitulatif

| # | Ajout | App | Pourquoi | Statut |
|---|-------|-----|----------|--------|
| 1 | Champ `reorder_level` sur `Product` | `catalog` | Seuil de réapprovisionnement du stock | ✅ Fait |
| 2 | Modèle abstrait `BasePartner` | `partners` | Factoriser les champs communs de `Customer` et `Supplier` | ✅ Fait |

---

## 1️⃣ Champ `reorder_level` sur `Product`

- **Type :** `DecimalField(max_digits=12, decimal_places=3, default=0)`
- **Contrainte :** `CHECK reorder_level >= 0` (`product_reorder_level_gte_0`)
- **Rôle :** quantité minimale en stock avant de devoir réapprovisionner.
- **Migration :** oui.

---

## 2️⃣ Modèle abstrait `BasePartner`

- **Champs :** `name`, `email`, `phone`, `address`, `is_active`
- **Particularité :** `abstract = True` → aucune table créée.
- **Héritiers :** `Customer`, `Supplier`
- **Contraintes :** unicité partielle sur `email`, avec un nom différent par modèle.
- **Migration :** probablement vide (schéma inchangé).

---

## 🆕 Modèle pour un nouvel ajout

Copie ce bloc et remplis-le :

```markdown
## N️⃣ Titre de l'ajout

- **Quoi :**
- **Où (app / fichier) :**
- **Pourquoi :**
- **Migration :** oui / non
- **Date :** JJ/MM/AAAA
```

---

## 📝 Règle

Chaque ajout hors plan = **une ligne dans le tableau** + **un court bloc** ci-dessus, et un commit dédié (`feat:` ou `refactor:`).
