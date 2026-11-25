"use client";
import {CatalogItemCompanies,type CatalogCompaniesProps} from '@/components/catalog-item-companies';
/** Vista aziendale autonoma: nessuna lettura implicita del catalogo organizzativo. */
export function CompanyCatalogItems(props:Omit<CatalogCompaniesProps,'itemId'>){return <CatalogItemCompanies {...props}/>;}
